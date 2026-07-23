import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import {
  classifyWorkerThrottleError,
  createWorkerCdpController,
  sanitizeCdpProtocolMessage,
  WorkerCdpAttachmentTimeoutError,
  type WorkerCdpController,
  type WorkerCdpTransport,
} from "./worker-cdp-controller";

interface Command {
  readonly id: number;
  readonly method: string;
  readonly params: Readonly<Record<string, unknown>>;
  readonly sessionId?: string;
}

type ResponseAction =
  | { readonly result: unknown }
  | { readonly error: { readonly code: number; readonly message: string } }
  | "hold";

class FakeTransport implements WorkerCdpTransport {
  readonly commands: Command[] = [];
  response: (command: Command) => ResponseAction = (command) => ({
    result:
      command.method === "Runtime.getHeapUsage"
        ? { usedSize: 10, totalSize: 20 }
        : {},
  });
  closeCalls = 0;
  sendError: Error | null = null;

  readonly #messageListeners = new Set<(message: unknown) => void>();
  readonly #closeListeners = new Set<() => void>();
  readonly #errorListeners = new Set<() => void>();

  send(message: string): void {
    if (this.sendError !== null) {
      throw this.sendError;
    }
    const command = JSON.parse(message) as Command;
    this.commands.push(command);
    const action = this.response(command);
    if (action !== "hold") {
      queueMicrotask(() => {
        if ("error" in action) {
          this.emit({ id: command.id, error: action.error });
        } else {
          this.emit({ id: command.id, result: action.result });
        }
      });
    }
  }

  async close(): Promise<void> {
    this.closeCalls += 1;
    this.emitClose();
  }

  onMessage(listener: (message: unknown) => void): () => void {
    this.#messageListeners.add(listener);
    return () => this.#messageListeners.delete(listener);
  }

  onClose(listener: () => void): () => void {
    this.#closeListeners.add(listener);
    return () => this.#closeListeners.delete(listener);
  }

  onError(listener: () => void): () => void {
    this.#errorListeners.add(listener);
    return () => this.#errorListeners.delete(listener);
  }

  emit(message: unknown): void {
    for (const listener of this.#messageListeners) {
      listener(message);
    }
  }

  emitJson(message: unknown): void {
    this.emit(JSON.stringify(message));
  }

  emitClose(): void {
    for (const listener of this.#closeListeners) {
      listener();
    }
  }

  emitError(): void {
    for (const listener of this.#errorListeners) {
      listener();
    }
  }

  respond(
    command: Command,
    action: Exclude<ResponseAction, "hold"> = { result: {} },
  ): void {
    if ("error" in action) {
      this.emit({ id: command.id, error: action.error });
    } else {
      this.emit({ id: command.id, result: action.result });
    }
  }

  attach(
    sessionId: string,
    type: "page" | "worker" | "other" = "worker",
    title = "mhwilds-browser-solver",
  ): void {
    this.emit({
      method: "Target.attachedToTarget",
      params: {
        sessionId,
        targetInfo: { type, title },
      },
    });
  }

  detach(sessionId: string): void {
    this.emit({
      method: "Target.detachedFromTarget",
      params: { sessionId },
    });
  }

  commandsFor(method: string): Command[] {
    return this.commands.filter((command) => command.method === method);
  }
}

const controllers: WorkerCdpController[] = [];

async function create(
  transport = new FakeTransport(),
  commandTimeoutMs = 1_000,
): Promise<{ controller: WorkerCdpController; transport: FakeTransport }> {
  const controller = await createWorkerCdpController({
    transport,
    commandTimeoutMs,
  });
  controllers.push(controller);
  return { controller, transport };
}

async function attachWorker(
  controller: WorkerCdpController,
  transport: FakeTransport,
  sessionId = "worker-session",
  title = "mhwilds-browser-solver",
) {
  const cursor = controller.captureWorkerAttachCursor();
  transport.attach(sessionId, "worker", title);
  return controller.waitForWorkerAfter(cursor);
}

async function flush(): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
}

afterEach(async () => {
  await Promise.all(controllers.splice(0).map((controller) => controller.close()));
});

describe("Worker CDP controller", () => {
  it("enables flattened recursive auto-attach at the browser root", async () => {
    const { transport } = await create();
    expect(transport.commands[0]).toMatchObject({
      method: "Target.setAutoAttach",
      params: {
        autoAttach: true,
        waitForDebuggerOnStart: true,
        flatten: true,
      },
    });
    expect(transport.commands[0]).not.toHaveProperty("sessionId");
  });

  it("applies initial rate 1 before resuming a newly attached Worker", async () => {
    const { controller, transport } = await create();
    const result = await attachWorker(controller, transport);
    expect(result).toMatchObject({
      requested_rate: 1,
      support: "applied",
      target_type: "worker",
    });
    const workerCommands = transport.commands.filter(
      ({ sessionId }) => sessionId === "worker-session",
    );
    expect(workerCommands.map(({ method }) => method)).toEqual([
      "Emulation.setCPUThrottlingRate",
      "Runtime.runIfWaitingForDebugger",
    ]);
  });

  it.each([0, -1, Number.NaN, Number.POSITIVE_INFINITY, 65])(
    "rejects invalid rate %s before sending a command",
    async (rate) => {
      const { controller, transport } = await create();
      const before = transport.commands.length;
      expect(() => controller.setRate(rate)).toThrow();
      expect(transport.commands).toHaveLength(before);
    },
  );

  it("reports zero active Workers without claiming application", async () => {
    const { controller } = await create();
    await expect(controller.setRate(4)).resolves.toEqual({
      requested_rate: 4,
      active_worker_count: 0,
      applied_count: 0,
      unsupported_count: 0,
      failed_count: 0,
      sessions: [],
    });
  });

  it("uses a stable timeout type when no new Worker is attached", async () => {
    const { controller } = await create();
    const cursor = controller.captureWorkerAttachCursor();
    await expect(controller.waitForWorkerAfter(cursor, 10)).rejects.toBeInstanceOf(
      WorkerCdpAttachmentTimeoutError,
    );
  });

  it("sends the exact command, params, and flat session envelope", async () => {
    const { controller, transport } = await create();
    await attachWorker(controller, transport, "worker-42");
    const summary = await controller.setRate(4);
    const command = transport
      .commandsFor("Emulation.setCPUThrottlingRate")
      .at(-1);
    expect(command).toEqual({
      id: expect.any(Number),
      method: "Emulation.setCPUThrottlingRate",
      params: { rate: 4 },
      sessionId: "worker-42",
    });
    expect(summary).toMatchObject({
      requested_rate: 4,
      active_worker_count: 1,
      applied_count: 1,
      unsupported_count: 0,
      failed_count: 0,
    });
  });

  it("recursively attaches a page, resumes it, and never counts it as a Worker", async () => {
    const { controller, transport } = await create();
    transport.attach("page-session", "page", "benchmark");
    await flush();
    expect(
      transport.commands.find(
        ({ method, sessionId }) =>
          method === "Target.setAutoAttach" && sessionId === "page-session",
      ),
    ).toMatchObject({
      params: {
        autoAttach: true,
        waitForDebuggerOnStart: true,
        flatten: true,
      },
    });
    expect(
      transport.commands.find(
        ({ method, sessionId }) =>
          method === "Runtime.runIfWaitingForDebugger" &&
          sessionId === "page-session",
      ),
    ).toBeDefined();
    expect((await controller.setRate(4)).active_worker_count).toBe(0);
  });

  it.each([
    {
      code: -32_601,
      message: "このメソッドはありません",
      label: "method-not-found code",
    },
    {
      code: -32_000,
      message: "Command is only supported on page targets.",
      label: "page-only message",
    },
    {
      code: -32_000,
      message: "Operation is only supported for pages, not workers",
      label: "Chromium page-only operation",
    },
  ])("records $label as unsupported and still resumes", async (protocolError) => {
    const transport = new FakeTransport();
    transport.response = (command) =>
      command.method === "Emulation.setCPUThrottlingRate"
        ? { error: protocolError }
        : { result: {} };
    const { controller } = await create(transport);
    const result = await attachWorker(controller, transport);
    expect(result).toMatchObject({
      support: "unsupported",
      protocol_error_code: protocolError.code,
      protocol_error_message: protocolError.message,
    });
    expect(
      transport.commandsFor("Runtime.runIfWaitingForDebugger"),
    ).toHaveLength(1);
    expect((await controller.setRate(4)).unsupported_count).toBe(1);
  });

  it("returns failed for an unexpected protocol error and poisons later work", async () => {
    const { controller, transport } = await create();
    await attachWorker(controller, transport);
    transport.response = (command) =>
      command.method === "Emulation.setCPUThrottlingRate"
        ? {
            error: {
              code: -32_000,
              message: "Unexpected internal target failure",
            },
          }
        : { result: {} };
    const summary = await controller.setRate(4);
    expect(summary).toMatchObject({ failed_count: 1, unsupported_count: 0 });
    expect(summary.sessions[0]).toMatchObject({
      support: "failed",
      protocol_error_code: -32_000,
    });
    expect(() => controller.setRate(1)).toThrow(
      "Worker CPU throttle application failed",
    );
  });

  it("attempts resume but exposes an unexpected attach setup failure", async () => {
    const transport = new FakeTransport();
    transport.response = (command) =>
      command.method === "Emulation.setCPUThrottlingRate"
        ? {
            error: {
              code: -32_000,
              message: "Unexpected internal target failure",
            },
          }
        : { result: {} };
    const { controller } = await create(transport);
    const cursor = controller.captureWorkerAttachCursor();
    transport.attach("worker-failed");
    await expect(controller.waitForWorkerAfter(cursor)).rejects.toThrow(
      "Worker CPU throttle setup failed",
    );
    expect(
      transport.commandsFor("Runtime.runIfWaitingForDebugger"),
    ).toHaveLength(1);
  });

  it("does not resume until attach-time rate application resolves", async () => {
    const transport = new FakeTransport();
    let held: Command | null = null;
    transport.response = (command) => {
      if (
        command.method === "Emulation.setCPUThrottlingRate" &&
        command.sessionId === "worker-held"
      ) {
        held = command;
        return "hold";
      }
      return { result: {} };
    };
    const { controller } = await create(transport);
    const cursor = controller.captureWorkerAttachCursor();
    transport.attach("worker-held");
    await flush();
    expect(held).not.toBeNull();
    expect(
      transport.commandsFor("Runtime.runIfWaitingForDebugger"),
    ).toHaveLength(0);
    transport.respond(held!);
    await expect(controller.waitForWorkerAfter(cursor)).resolves.toMatchObject({
      support: "applied",
    });
    expect(
      transport.commandsFor("Runtime.runIfWaitingForDebugger"),
    ).toHaveLength(1);
  });

  it("waits for every active Worker response", async () => {
    const { controller, transport } = await create();
    await attachWorker(controller, transport, "worker-a");
    await attachWorker(controller, transport, "worker-b");
    const held: Command[] = [];
    transport.response = (command) => {
      if (command.method === "Emulation.setCPUThrottlingRate") {
        held.push(command);
        return "hold";
      }
      return { result: {} };
    };
    let settled = false;
    const application = controller.setRate(4).then((value) => {
      settled = true;
      return value;
    });
    await flush();
    expect(held).toHaveLength(2);
    transport.respond(held[0]!);
    await flush();
    expect(settled).toBe(false);
    transport.respond(held[1]!);
    await expect(application).resolves.toMatchObject({
      active_worker_count: 2,
      applied_count: 2,
    });
  });

  it("reapplies a changed current rate before resuming an attaching Worker", async () => {
    const transport = new FakeTransport();
    let firstApply: Command | null = null;
    transport.response = (command) => {
      if (
        command.method === "Emulation.setCPUThrottlingRate" &&
        command.sessionId === "worker-race" &&
        firstApply === null
      ) {
        firstApply = command;
        return "hold";
      }
      return { result: {} };
    };
    const { controller } = await create(transport);
    const cursor = controller.captureWorkerAttachCursor();
    transport.attach("worker-race");
    await flush();
    const rateChange = controller.setRate(4);
    await flush();
    transport.respond(firstApply!);
    await controller.waitForWorkerAfter(cursor);
    await rateChange;
    const methods = transport.commands
      .filter(({ sessionId }) => sessionId === "worker-race")
      .map(({ method, params }) => ({ method, params }));
    const resumeIndex = methods.findIndex(
      ({ method }) => method === "Runtime.runIfWaitingForDebugger",
    );
    expect(
      methods
        .slice(0, resumeIndex)
        .filter(({ method }) => method === "Emulation.setCPUThrottlingRate"),
    ).toEqual([
      { method: "Emulation.setCPUThrottlingRate", params: { rate: 1 } },
      { method: "Emulation.setCPUThrottlingRate", params: { rate: 4 } },
    ]);
  });

  it("makes a later Worker inherit the current rate", async () => {
    const { controller, transport } = await create();
    await controller.setRate(4);
    const result = await attachWorker(controller, transport, "worker-new");
    expect(result.requested_rate).toBe(4);
    expect(
      transport
        .commandsFor("Emulation.setCPUThrottlingRate")
        .find(({ sessionId }) => sessionId === "worker-new"),
    ).toMatchObject({ params: { rate: 4 } });
  });

  it("waits for detach and never sends to the detached session", async () => {
    const { controller, transport } = await create();
    await attachWorker(controller, transport, "worker-old");
    let detached = false;
    const waiting = controller.waitForWorkersDetached().then(() => {
      detached = true;
    });
    await flush();
    expect(detached).toBe(false);
    transport.detach("worker-old");
    await waiting;
    const before = transport.commands.length;
    expect((await controller.setRate(4)).active_worker_count).toBe(0);
    expect(transport.commands).toHaveLength(before);
  });

  it("records an in-flight detach as failed evidence", async () => {
    const { controller, transport } = await create();
    await attachWorker(controller, transport, "worker-detaching");
    transport.response = (command) =>
      command.method === "Emulation.setCPUThrottlingRate" ? "hold" : { result: {} };
    const application = controller.setRate(4);
    await flush();
    transport.detach("worker-detaching");
    await expect(application).resolves.toMatchObject({ failed_count: 1 });
  });

  it("rejects pending work on transport close or error", async () => {
    for (const signal of ["close", "error"] as const) {
      const { controller, transport } = await create();
      await attachWorker(controller, transport, `worker-${signal}`);
      transport.response = (command) =>
        command.method === "Emulation.setCPUThrottlingRate"
          ? "hold"
          : { result: {} };
      const application = controller.setRate(4);
      await flush();
      if (signal === "close") transport.emitClose();
      else transport.emitError();
      await expect(application).resolves.toMatchObject({ failed_count: 1 });
      expect(() => controller.setRate(1)).toThrow(/transport/iu);
    }
  });

  it.each([
    "not-json",
    JSON.stringify({ id: "bad", result: {} }),
  ])("rejects malformed transport input %s", async (message) => {
    const { controller, transport } = await create();
    transport.emit(message);
    expect(() => controller.setRate(4)).toThrow(/malformed/iu);
  });

  it("records a malformed pending response as failed", async () => {
    const { controller, transport } = await create();
    await attachWorker(controller, transport, "worker-malformed");
    let held: Command | null = null;
    transport.response = (command) => {
      if (command.method === "Emulation.setCPUThrottlingRate") {
        held = command;
        return "hold";
      }
      return { result: {} };
    };
    const application = controller.setRate(4);
    await flush();
    transport.emit({
      id: held!.id,
      error: { code: "bad", message: 1 },
    });
    await expect(application).resolves.toMatchObject({ failed_count: 1 });
  });

  it("turns command timeout and send throw into failed evidence", async () => {
    const timeoutTransport = new FakeTransport();
    const timeoutController = (
      await create(timeoutTransport, 10)
    ).controller;
    await attachWorker(timeoutController, timeoutTransport, "worker-timeout");
    timeoutTransport.response = (command) =>
      command.method === "Emulation.setCPUThrottlingRate"
        ? "hold"
        : { result: {} };
    await expect(timeoutController.setRate(4)).resolves.toMatchObject({
      failed_count: 1,
    });

    const { controller, transport } = await create();
    await attachWorker(controller, transport, "worker-send");
    transport.sendError = new Error("send broke");
    await expect(controller.setRate(4)).resolves.toMatchObject({
      failed_count: 1,
    });
  });

  it("resends the same rate deterministically", async () => {
    const { controller, transport } = await create();
    await attachWorker(controller, transport);
    const before = transport.commandsFor(
      "Emulation.setCPUThrottlingRate",
    ).length;
    const first = await controller.setRate(1);
    const second = await controller.setRate(1);
    expect(first).toEqual(second);
    expect(
      transport.commandsFor("Emulation.setCPUThrottlingRate"),
    ).toHaveLength(before + 2);
  });

  it("samples the latest active Worker heap using its session envelope", async () => {
    const { controller, transport } = await create();
    await attachWorker(controller, transport, "worker-heap");
    await expect(controller.sampleWorkerHeap()).resolves.toEqual({
      usedSize: 10,
      totalSize: 20,
    });
    expect(
      transport.commands
        .filter(
          ({ method }) =>
            method === "HeapProfiler.collectGarbage" ||
            method === "Runtime.getHeapUsage",
        )
        .map(({ method, sessionId }) => ({ method, sessionId })),
    ).toEqual([
      {
        method: "HeapProfiler.collectGarbage",
        sessionId: "worker-heap",
      },
      { method: "Runtime.getHeapUsage", sessionId: "worker-heap" },
    ]);
  });

  it("keeps internal identifiers out of the public result and preserves inputs", async () => {
    const { controller, transport } = await create();
    const title = "solver Worker";
    await attachWorker(
      controller,
      transport,
      "private-session-id",
      title,
    );
    const summary = await controller.setRate(4);
    expect(JSON.stringify(summary)).not.toContain("private-session-id");
    expect(JSON.stringify(summary)).not.toContain("webSocketDebuggerUrl");
    expect(summary.sessions[0]?.target_title).toBe(title);
    expect(title).toBe("solver Worker");
  });

  it("closes idempotently and rejects operations after close", async () => {
    const { controller, transport } = await create();
    const first = controller.close();
    const second = controller.close();
    await Promise.all([first, second]);
    expect(transport.closeCalls).toBe(1);
    expect(() => controller.setRate(4)).toThrow("closed");
  });
});

describe("Worker throttle error classification", () => {
  it.each([
    [-32_601, "localized message"],
    [-32_000, "'Emulation.setCPUThrottlingRate' wasn't found"],
    [-32_000, "Emulation domain is not available for this target"],
    [-32_001, "Target type worker does not support the emulation domain"],
  ])("classifies known unsupported error %i", (code, message) => {
    expect(classifyWorkerThrottleError({ code, message })).toBe("unsupported");
  });

  it.each([
    [-32_000, "Unexpected internal target failure"],
    [-32_000, ""],
    [-1, "Command is only supported on page targets."],
  ])("keeps unrelated error %i failed", (code, message) => {
    expect(classifyWorkerThrottleError({ code, message })).toBe("failed");
  });

  it("sanitizes multiline protocol text without retaining a stack", () => {
    expect(
      sanitizeCdpProtocolMessage(
        "Command is only supported on page targets.\n    at private-session",
      ),
    ).toBe("Command is only supported on page targets.");
    expect(sanitizeCdpProtocolMessage("")).toBe("CDP command failed");
  });
});

describe("Worker controller source audit", () => {
  it("contains the real Worker command and none of the prior no-op patterns", async () => {
    const source = await readFile(
      resolve(process.cwd(), "src/browser-solver/worker-cdp-controller.ts"),
      "utf8",
    );
    expect(source).toContain('"Emulation.setCPUThrottlingRate"');
    expect(source).toContain("session.sessionId");
    expect(source).not.toContain(["void", "workerSessions"].join(" "));
    expect(source).not.toContain(["void", "rate"].join(" "));
    expect(source).not.toContain(".catch(() => undefined)");
  });
});

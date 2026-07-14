import { Container } from "@cloudflare/containers";

import handler from "./handler.mjs";

export class SearchApiContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "10m";
}

export default handler;

# MHWILDS スキルシミュレータ API Worker

## アーキテクチャ

公開画面とStatic Assetsは既存Worker `mhwilds-skill-sim`が引き続き配信します。よりspecificな次のCustom Routeだけを、新しいWorker `mhwilds-skill-sim-api`へ割り当てます。

```text
Browser
  -> trinitrotorol.com/game-guide/mhwilds-skill-sim/api/*
  -> Worker: mhwilds-skill-sim-api
  -> Durable Object binding: SEARCH_API
  -> named Container instance: production
  -> Container class: SearchApiContainer
  -> FastAPI + OR-Tools + production Catalog (port 8080)
```

Containerは`basic`、最大1 instanceです。Workerは公開する3 endpointだけを同じnamed instanceへ転送し、任意pathをproxyしません。

```text
GET  /game-guide/mhwilds-skill-sim/api/health
GET  /game-guide/mhwilds-skill-sim/api/catalog/metadata
POST /game-guide/mhwilds-skill-sim/api/search/cp-sat/ranked
```

## 課金とproduction deployの前提

Cloudflare ContainersにはWorkers Paid planが必要で、利用により課金が発生し得ます。Codexはplanの購入・変更、支払方法や課金設定の変更を行いません。production deployは次の前提をすべて確認できた場合だけ手動で実行します。

- 対象accountでWorkers Paidが有効
- GitHub ActionsからDockerを利用可能
- repository secrets `CLOUDFLARE_ACCOUNT_ID`と`CLOUDFLARE_API_TOKEN`が存在
- tokenが対象accountと`trinitrotorol.com` zoneだけに限定され、Worker/Containerのdeployとroute更新に必要な最小権限だけを持つ
- Task 065のproduction deployが承認済み

secretは名前の存在だけを確認し、値をrepository、log、artifact、READMEへ出力しません。前提が不足する場合はworkflowをdispatchせず、課金変更や権限回避をせずに停止します。

## Manual GitHub Actions deployment

`.github/workflows/deploy-cloudflare-api.yml`は`workflow_dispatch`専用です。push、pull request、scheduleでは起動せず、production API deployを直列化します。frontendの既存Cloudflare Git integrationとは独立しています。

前提確認と全repository verification、commit、pushの完了後に、GitHub側でworkflowがparseできることを確認してから手動起動します。

```console
gh workflow view deploy-cloudflare-api.yml
gh workflow run deploy-cloudflare-api.yml --ref master
gh run list --workflow deploy-cloudflare-api.yml
gh run watch RUN_ID
```

workflowはPython 3.12でprojectとcontract testsを実行し、live Catalogを生成・検証してからNode testsとDocker smokeを行います。その後、Wrangler `4.110.0`でWorker/Containerをdeployし、Container一覧と公開APIを確認します。初回provisioningは最大10分のbounded retryで待ち、503やtimeoutを成功として扱いません。

## Live Catalog

production Catalogはdeploy runごとに既存MHDB normalizerで生成します。

```text
raw snapshot: $RUNNER_TEMP/mhdb-raw
Catalog:      .build/production/catalog.json
```

生成後に`load_catalog`で再読込し、`schema_version == 1`、skills/equipment/decorationsのnon-empty counts、empty requirements/preferencesかつ`max_results=1`のranked検索を検証します。countとchecksumだけをlogし、Catalog全体は出力しません。live syncに失敗した場合は古いCatalogへfallbackせずdeployを停止します。

raw snapshotとproduction CatalogはGitへcommitせず、GitHub Actions artifactにもuploadしません。Docker imageには検証済みCatalogだけをCOPYします。

## Local Docker smoke

Dockerが利用可能な環境では、tiny Catalogでimageとruntimeを検証できます。

```console
mkdir -p .build/production
cp data/fixtures/tiny_catalog.json .build/production/catalog.json
docker build --platform linux/amd64 --file Dockerfile.api --tag mhwilds-skill-sim-api:task065 .
docker run --detach --name mhwilds-skill-sim-api-task065 --publish 127.0.0.1:18080:8080 --memory 1g --cpus 0.25 mhwilds-skill-sim-api:task065
```

`/health`、`/catalog/metadata`、empty requirements/preferencesかつ`max_results=1`の`/search/cp-sat/ranked`を確認します。さらにruntime UIDがnon-rootであること、Docker healthcheckが`healthy`になること、Container logにsecretやrequest bodyがないことを確認します。終了時は成功・失敗にかかわらずContainerを停止・削除します。

```console
docker rm --force mhwilds-skill-sim-api-task065
```

Dockerを利用できない場合はimage未検証のままproduction deployしません。

## API制限

ranked POSTはCloudflare Rate Limiting bindingでclient IPとrouteごとに`5 requests / 60 seconds`へ制限します。超過時は429、`Retry-After: 60`、`search rate limit exceeded`を返します。healthとmetadataはこの制限の対象外です。

ranked requestはmedia typeが`application/json`である必要があり、body上限は64 KiBです。WorkerはCookie、Authorization、client IP headerをContainerへ転送せず、全responseに`Cache-Control: no-store`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`を設定します。CORS、認証、新しい公開endpointは追加しません。

## Production smoke

deploy後は次のURLを直接確認します。

```text
https://trinitrotorol.com/game-guide/mhwilds-skill-sim/api/health
https://trinitrotorol.com/game-guide/mhwilds-skill-sim/api/catalog/metadata
https://trinitrotorol.com/game-guide/mhwilds-skill-sim/api/search/cp-sat/ranked
```

healthとmetadataが200、metadata countsがnon-empty、ranked payload `{"requirements":[],"preferences":[],"max_results":1}`が200でcandidate 1件、`preference_score` 0、`timed_out` falseになることを確認します。404、405、415、security headers、CORS wildcard・Set-Cookie・stack traceがないことも確認します。production rate limitを確認するために短時間で5回を超える実検索を送りません。

公開UI `https://trinitrotorol.com/game-guide/mhwilds-skill-sim/`は実browserでdesktop `1440 x 900`とmobile `390 x 844`を確認します。Catalog counts、武器種select、必須・優先スキル追加、表示件数、準備中表示が消えること、empty条件でのcandidate、優先スコア、7部位装備、発動スキル、responsive layout、horizontal overflow、JS/CSS、network、consoleを検証します。既存guide `https://trinitrotorol.com/game-guide/exponential-idle-minigame-guide`もHTTP 200と実browser表示を確認します。

## Troubleshooting

- plan、secret、token scope、Dockerのいずれかが不足している場合はdispatchしません。planや課金を自動変更しません。
- live sync失敗時はnetwork/MHDB responseを確認し、古いCatalogへ差し替えません。
- image build失敗時はDockerfileとallowlist型`.dockerignore`を確認します。検証なしでdeployを続行しません。
- deploy失敗時はplan不足、secret不足、permission不足、route衝突、image build、Container provisioning、live syncをlogから区別します。force deployやsecurity bypassを行いません。
- healthが503の間はprovisioning完了として扱いません。bounded retryがtimeoutした場合はrunを失敗させ、response bodyやsecretをlogへ出しません。
- rate limit namespace IDが対象account内で衝突した場合は既存bindingを上書きせず、未使用の整数IDへ最小変更します。

## Rollback

API Workerのspecific routeを解除するか、API Workerを旧deploymentへrollbackします。specific routeがなくなると既存frontend WorkerがAPI pathを再び受け、現在の503 fallbackへ戻ります。

rollbackではfrontend Static Assetsと既存Cloudflare Git integrationを削除・変更しません。production Catalogはrepositoryへcommitされないため、repositoryから復元しようとしません。

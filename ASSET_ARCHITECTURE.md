# Asset architecture

本專案的圖片、音訊、MIDI 與 PDF 是整理後的成果，不再由 Git 保存。檔案仍保留在本機的 `docs/`，正式部署時則由 Cloudflare R2 提供給網站。

## 目錄與責任

```text
本機 docs/                         整理與編輯素材
        │
        │ scripts/sync_media_to_r2.sh
        ▼
Cloudflare R2: <bucket>/reshoka/    正式素材來源
        │
        │ GitHub Actions checkout 後下載
        ▼
CI 的 docs/                         MkDocs 建置輸入
        │
        ├─ mkdocs build
        ├─ 將網站媒體引用改成 R2 URL
        └─ 從 Pages artifact 移除媒體檔
```

Git 只保存程式碼、Markdown、TMD、設定與同步腳本。`docs/` 下的下列副檔名會被 `.gitignore` 忽略：

```text
jpg jpeg png mp3 wav mid pdf
```

## 本機上傳

先安裝 AWS CLI。它只是用來呼叫 Cloudflare R2 的 S3-compatible API，不會把檔案傳到 AWS。

```bash
brew install awscli
```

在目前 shell 設定 R2 S3 credentials：

```bash
export R2_ACCESS_KEY_ID="..."
export R2_SECRET_ACCESS_KEY="..."
export R2_ENDPOINT="https://<ACCOUNT_ID>.r2.cloudflarestorage.com"
export R2_BUCKET="<bucket-name>"
```

接著先做 dry run：

```bash
./scripts/sync_media_to_r2.sh --dryrun
```

確認清單後正式同步：

```bash
./scripts/sync_media_to_r2.sh
```

同步目的地是：

```text
s3://${R2_BUCKET}/reshoka/
```

腳本使用 `aws s3 sync`，只會上傳新增或變更的檔案；目前沒有 `--delete`，所以不會因為本機少了檔案而刪除 R2 上的物件。

如需使用不同的本機素材根目錄或 R2 prefix：

```bash
MEDIA_ROOT=/path/to/docs R2_PREFIX=reshoka ./scripts/sync_media_to_r2.sh --dryrun
```

## Cloudflare token 位置

Cloudflare Dashboard：

1. 開啟 **R2 → Overview**。
2. 在 **Account Details** 選 **Manage API Tokens**。
3. 建立 Account API Token。
4. 權限選 **Object Read & Write**，最好限制到指定 bucket。
5. 複製 Access Key ID 與 Secret Access Key。

Secret Access Key 只會顯示一次，不要提交到 Git，也不要寫入這個文件。

Endpoint 通常是：

```text
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

## GitHub Actions

`.github/workflows/deploy.yml` 會在建站前從 R2 還原媒體，讓不含媒體檔的 checkout 仍可執行 MkDocs；CI 不會再次上傳媒體。素材的上傳責任在本機的 `scripts/sync_media_to_r2.sh`，建站後只執行 URL externalization 與 Pages 部署。

GitHub repo 的 **Settings → Secrets and variables → Actions** 需要下列 secrets：

```text
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_ENDPOINT
R2_BUCKET
R2_PUBLIC_BASE_URL
```

`R2_PUBLIC_BASE_URL` 是網站瀏覽器實際使用的公開 R2 base URL，不一定等於 S3 API endpoint。

## 新增或修改素材的流程

1. 將素材放入正確的 `docs/` 子目錄。
2. 確認 Markdown 或資料索引使用正確的相對路徑。
3. 執行 `./scripts/sync_media_to_r2.sh --dryrun`。
4. 確認只包含預期變更後，執行 `./scripts/sync_media_to_r2.sh`。
5. 提交對應的 Markdown、TMD 或程式碼變更；媒體本身不會進入 Git。

## 注意事項

- 不要把 R2 secret 寫進 shell script、`.env`、Markdown 或 GitHub workflow。
- 不要對 R2 sync 加上 `--delete`，除非已確認遠端多出的物件確實應刪除。
- Git working tree 裡看不到媒體檔的變更是預期行為，因為它們被 `.gitignore` 忽略。
- 新機器需要先從 R2 還原素材，或執行完整的 CI restore 流程，才會有完整的 `docs/` 媒體檔。
- 若要改寫 GitHub `main` 歷史，先確認 R2 素材完整、GitHub secrets 正確，再使用受保護的 force push 流程。

Cloudflare R2 API token 說明：

<https://developers.cloudflare.com/r2/api/tokens/>

Cloudflare R2 S3 CLI 說明：

<https://developers.cloudflare.com/r2/get-started/cli/>

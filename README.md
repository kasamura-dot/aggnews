# AggNews

主要ニュースサイトの見出しリンクを、**公式RSSのみ**から収集して表示するWebアプリです。

## 重要: 法律・利用規約順守ポリシー
- 取得元は `news_server.py` / `scripts/build_headlines.py` 内の許可リスト（公式RSS URL）に限定
- HTML本文スクレイピングは行わない
- 表示は見出し・リンク・公開日時・RSSに含まれる画像のみ
- 各ソースカードに利用規約リンクを表示

## 収録サイト
- NHK
- BBC World
- CBS World
- CNN World
- NYTimes World
- The Guardian World
- Al Jazeera
- UN News
- NPR
- DW
- France 24

## ファイル
- `index.html`: 画面レイアウト
- `styles.css`: スタイル
- `app.js`: フロント描画ロジック（API + JSONフォールバック）
- `news_server.py`: ローカルAPIサーバー
- `scripts/build_headlines.py`: 静的 `headlines.json` 生成（DeepL翻訳対応）
- `.github/workflows/update-headlines.yml`: 定期更新ジョブ

## 動作モード
- ローカル開発: `python news_server.py` を起動し `http://127.0.0.1:8000` で利用
- GitHub Pages: `headlines.json` を配信して利用（サーバー不要）

## GitHub Pages での必須設定
1. このリポジトリに push
2. `Settings > Secrets and variables > Actions` で `DEEPL_API_KEY` を作成（任意、和訳する場合）
3. Actions タブで `Update headlines.json` を `Run workflow`
4. リポジトリ直下に `headlines.json` が更新コミットされることを確認
5. GitHub Pages を有効化して公開

## エラー対処
- `API error (404)`:
  - `/api/headlines` が無いホストで開いています
  - GitHub Pagesなら `headlines.json` 生成（Actions実行）を確認
- `Failed to fetch`:
  - ネットワークまたはCORSの問題
  - ローカルは `python news_server.py` 起動状態を確認

## 和訳について
- 英語見出しの和訳は `translated_title` で表示します。
- ローカル実行: `DEEPL_API_KEY` を環境変数で設定すると有効化されます。
- GitHub Pages: リポジトリシークレット `DEEPL_API_KEY` を設定すると、Actions生成の `headlines.json` に和訳が入ります。

## 注意
- 本実装は法的助言ではありません。運用前に各媒体の最新利用規約・配信条件を必ず確認してください。
- 規約変更があった媒体はソース許可リストから外してください。

## ライセンス
MIT

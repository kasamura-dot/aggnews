# AggNews

主要ニュースサイトの見出しリンクを、**公式RSSのみ**から収集して表示するWebアプリです。

## 重要: 法律・利用規約順守ポリシー
- 取得元は `news_server.py` 内の許可リスト（公式RSS URL）に限定
- HTML本文スクレイピングは行わない
- 表示は見出し・リンク・公開日時・RSSに含まれる画像のみ
- 取得間隔はサーバー側でキャッシュ（デフォルト10分）し、過剰アクセスを回避
- 各ソースカードに利用規約リンクを表示

## 収録サイト（増量済み）
- NHK
- BBC World
- Reuters World
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
- `app.js`: フロント描画ロジック（`/api/headlines` を利用）
- `news_server.py`: 公式RSS取得API + 静的ファイル配信

## 使い方
1. `python news_server.py`
2. ブラウザで `http://127.0.0.1:8000` を開く
3. 表示件数を選んで `更新`

## 起動確認
- API疎通確認: `http://127.0.0.1:8000/api/headlines?limit=5`
- `Failed to fetch` が出る場合:
  - `python news_server.py` が起動中か確認
  - `index.html` を `file://` 直開きではなく `http://127.0.0.1:8000` で開く

## 和訳について
- 規約順守のため、翻訳はデフォルト無効です。
- DeepL公式APIを使う場合のみ有効化できます。
- 有効化手順: 環境変数 `DEEPL_API_KEY` を設定して `news_server.py` を起動

## 注意
- 本実装は法的助言ではありません。運用前に各媒体の最新利用規約・配信条件を必ず確認してください。
- 規約変更があった媒体は、`news_server.py` の許可リストから外してください。

## ライセンス
MIT

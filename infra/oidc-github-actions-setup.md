# GitHub Actions (OIDC) → AWS (CDK) セットアップ手順

このリポジトリの `main` への push/merge をトリガとして、GitHub Actions から AWS CDK をデプロイするための
OIDC（OpenID Connect）設定の手順です。

> 注: 本ドキュメントは「一度だけ」必要な AWS 側初期設定です。ワークフロー自体はリポジトリにより提供されますが、
> 最初の `cdk-deploy-role` と OIDC Provider を事前に作成する必要があります。

## 前提

- AWS Account ID: `051866032261`
- デプロイリージョン: `us-east-1`
- GitHub リポジトリ: `PheasantDevil/ebay-auto-seller`
- IAM Role 名: `cdk-deploy-role`
- ブランチ: `main` のみ

## 1. OIDC Provider を作成

GitHub Actions の OIDC Provider URL は以下です。

- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

`thumbprint` は GitHub 側の証明書事情で複数あるため、両方追加します。

- `6938fd4d98bab03faadb97b34396831e3780aea1`
- `1c58a3a8518e8759bf075b76b750d4f2df264fcd`

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 1c58a3a8518e8759bf075b76b750d4f2df264fcd
```

すでに作成済みの場合は失敗することがあります（その場合は読み飛ばしてください）。

## 2. IAM Role を作成（Trust Policy）

信頼（assume）を許可する条件:

- Federated principal: `arn:aws:iam::051866032261:oidc-provider/token.actions.githubusercontent.com`
- `aud` = `sts.amazonaws.com`
- `sub` = `repo:PheasantDevil/ebay-auto-seller:ref:refs/heads/main`

Trust policy（`trust-policy.json`）を作成します。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::051866032261:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:PheasantDevil/ebay-auto-seller:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

```bash
aws iam create-role \
  --role-name cdk-deploy-role \
  --assume-role-policy-document file://trust-policy.json
```

## 3. 権限（Permissions Policy）

まずは CDK bootstrap + deploy が通るため、ロールに `AdministratorAccess` を一時的に付与してください。
通った後に最小権限へ絞り込みます。

```bash
aws iam attach-role-policy \
  --role-name cdk-deploy-role \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

## 4. 動作確認

以後、`main` への push/merge で `.github/workflows/infra-deploy.yml` が走り、CDK の bootstrap→synth→deploy が行われます。


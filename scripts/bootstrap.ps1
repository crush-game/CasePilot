$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot '.env'
if (Test-Path -LiteralPath $envPath) {
    Write-Output '本地配置已存在，保留原文件。'
    exit 0
}
$localPassword = [guid]::NewGuid().ToString('N')
$lines = @(
    "POSTGRES_PASSWORD=$localPassword"
    'POSTGRES_PORT=55432'
    "AFTERSALES_DATABASE_URL=postgresql://aftersales:${localPassword}@127.0.0.1:55432/aftersales"
    "AFTERSALES_TEST_DATABASE_URL=postgresql://aftersales:${localPassword}@127.0.0.1:55432/aftersales_test"
    'AFTERSALES_MODEL_PROVIDER=mock'
    'AFTERSALES_ENTERPRISE_DATA_PROVIDER=mock'
)
$lines | Set-Content -LiteralPath $envPath -Encoding utf8
Write-Output '已生成仅供本机使用的随机数据库配置（不输出凭据）。'

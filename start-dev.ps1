$ErrorActionPreference = 'Stop'

$pgCtl = 'C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe'
$data = Join-Path $PSScriptRoot '.postgres-data'
$log = Join-Path $PSScriptRoot '.postgres.log'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pgCtl -PathType Leaf)) {
    throw "PostgreSQL 17 was not found at $pgCtl."
}
if (-not (Test-Path -LiteralPath (Join-Path $data 'PG_VERSION') -PathType Leaf)) {
    throw 'The local PostgreSQL cluster is missing. See README.md for setup with another database.'
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'The project virtual environment is missing. Follow the setup steps in README.md.'
}

& $pgCtl -D $data status
if ($LASTEXITCODE -ne 0) {
    & $pgCtl -D $data -l $log -o '-h 127.0.0.1 -p 55439' -w start
    if ($LASTEXITCODE -ne 0) {
        throw 'PostgreSQL failed to start. See .postgres.log for details.'
    }
}

& $python (Join-Path $PSScriptRoot 'app\main.py')
exit $LASTEXITCODE

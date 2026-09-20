param(
  [Parameter(Mandatory=$true)][string]$Config,
  [Parameter(Mandatory=$true)][string]$SecretsOut
)
# gen_secrets.ps1 — replaces placeholder secrets in grok2api config.yaml (Windows, no openssl needed)
$ErrorActionPreference = "Stop"

$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$jwt = -join ($bytes | ForEach-Object { $_.ToString("x2") })

$credBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($credBytes)
$cred = [Convert]::ToBase64String($credBytes)   # MUST be base64 of exactly 32 bytes

$pwBytes = New-Object byte[] 15
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($pwBytes)
$adminPw = [Convert]::ToBase64String($pwBytes) -replace '[/+=]', ''

$t = Get-Content $Config -Raw -Encoding UTF8
if ($t -match 'replace-with') {
  $t = $t -replace 'jwtSecret: "[^"]*"', "jwtSecret: `"$jwt`""
  $t = $t -replace 'credentialEncryptionKey: "[^"]*"', "credentialEncryptionKey: `"$cred`""
  $t = $t -replace '(?s)(bootstrapAdmin:.{0,300}?password: )"[^"]*"', "`$1`"$adminPw`""
  Set-Content $Config $t -Encoding UTF8 -NoNewline
  Set-Content $SecretsOut "admin user: admin`nadmin password: $adminPw`njwtSecret: $jwt`ncredentialEncryptionKey: $cred" -Encoding UTF8
  Write-Host "[+] secrets generated -> $SecretsOut"
} else {
  Write-Host "[*] config already has real secrets, skipping"
}

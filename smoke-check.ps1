$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$botFile = Join-Path $root "logbot.py"

if (-not (Test-Path $botFile)) {
    throw "logbot.py bulunamadi."
}

$content = Get-Content $botFile -Raw
$checks = @()

$checks += [pscustomobject]@{
    Name = "Help command wired"
    Ok = $content -match "await gelismis_yardim\(ctx\)"
    Detail = "yardim komutu yeni yardim ekranina yonlenmeli."
}

$checks += [pscustomobject]@{
    Name = "Auto log command exists"
    Ok = $content -match '@bot\.command\(name="logkur"'
    Detail = ".logkur komutu mevcut olmali."
}

$checks += [pscustomobject]@{
    Name = "No leaked warn code in settings loader"
    Ok = $content -notmatch 'varsayilan_kanallari_yukle\(guild_id: int\):[\s\S]{0,500}hedef_uye_bul'
    Detail = "Ayar yukleme fonksiyonuna yanlis komut satirlari sizmamali."
}

$checks += [pscustomobject]@{
    Name = "Kick reply support exists"
    Ok = $content -match 'async def kick\(ctx, uye: discord\.Member = None, \*, sebep: str = "Sebep belirtilmedi"\):[\s\S]{0,300}hedef_uye_bul'
    Detail = ".kick reply ile hedef alabilmeli."
}

$checks += [pscustomobject]@{
    Name = "Warn reply support exists"
    Ok = $content -match 'async def warn\(ctx, uye: discord\.Member = None, \*, sebep: str = "Sebep belirtilmedi"\):[\s\S]{0,300}hedef_uye_bul'
    Detail = ".warn reply ile hedef alabilmeli."
}

$failed = $checks | Where-Object { -not $_.Ok }

foreach ($check in $checks) {
    $status = if ($check.Ok) { "OK" } else { "FAIL" }
    Write-Host ("[{0}] {1}" -f $status, $check.Name)
    if (-not $check.Ok) {
        Write-Host ("  -> {0}" -f $check.Detail)
    }
}

if ($failed) {
    throw ("Smoke check basarisiz: {0} hata" -f $failed.Count)
}

Write-Host "Tum smoke check kontrolleri gecti."

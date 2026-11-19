#!/bin/bash
# Sobe um arquivo grande para uma pasta do Google Drive (upload retomavel, pedacos de 256 MiB).
#   tools/drive_upload.sh <arquivo> [folder_id] [nome]
# Requer credencial 'www.googleapis.com' salva no ambiente (ferramenta request_credential; token OAuth com escopo drive/drive.file, vale ~1 h).
# O proxy injeta o token: NAO passe Authorization aqui. Imprime o link ao terminar.
set -e
F="$1"; FOLDER="${2:-1zvlboOsBRSv1icTJDJ2KA0DPaT0M_EmQ}"; NAME="${3:-$(basename "$F")}"
TOTAL=$(stat -c %s "$F"); T=$(mktemp -d)
curl -sS -m 60 -D $T/h -o $T/i -X POST "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true" \
  -H "Content-Type: application/json; charset=UTF-8" -H "X-Upload-Content-Type: video/mp4" -H "X-Upload-Content-Length: $TOTAL" \
  -d "{\"name\":\"$NAME\",\"parents\":[\"$FOLDER\"]}"
URL=$(grep -i '^location' $T/h | sed 's/^[Ll]ocation: //' | tr -d '\r'); [ -n "$URL" ] || { echo "falha ao iniciar:"; cat $T/h $T/i; exit 1; }
CH=$((256*1024*1024)); off=0
while [ $off -lt $TOTAL ]; do
  end=$((off+CH-1)); [ $end -ge $TOTAL ] && end=$((TOTAL-1)); len=$((end-off+1))
  code=$(tail -c +$((off+1)) "$F" | head -c $len | curl -sS -m 1800 -o $T/r -w "%{http_code}" -X PUT "$URL" -H "Content-Type: video/mp4" -H "Content-Length: $len" -H "Content-Range: bytes $off-$end/$TOTAL" --data-binary @-)
  echo "bytes $off-$end -> $code"
  case $code in 308) off=$((end+1));; 200|201) ID=$(python3 -c "import json;print(json.load(open('$T/r'))['id'])"); echo "OK: https://drive.google.com/file/d/$ID/view"; exit 0;; *) echo "ERRO $code"; head -c 400 $T/r; exit 1;; esac
done

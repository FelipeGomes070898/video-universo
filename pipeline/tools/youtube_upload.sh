#!/bin/bash
# Sobe um MP4 para o YouTube como PRIVADO (upload retomavel, pedacos de 256 MiB) + thumbnail.
#   tools/youtube_upload.sh <video.mp4> <metadata.json> [thumbnail.jpg]
# SEM tokens aqui: o token (OAuth, escopo youtube.upload, ~1 h) e injetado pelo proxy do ambiente (request_credential, host www.googleapis.com).
# NAO passe Authorization. O header Content-Type: video/mp4 e obrigatorio (senao o proxy recusa o corpo como formulario).
# metadata.json: {"snippet":{"title","description","tags":[...],"categoryId":"28","defaultLanguage":"en","defaultAudioLanguage":"en"},
#                 "status":{"privacyStatus":"private","selfDeclaredMadeForKids":false,"containsSyntheticMedia":true,"embeddable":true}}
set -e
F="$1"; META="$2"; THUMB="$3"; TOTAL=$(stat -c %s "$F"); T=$(mktemp -d)
curl -sS -m 60 -D $T/h -o $T/i -X POST "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status" \
  -H "Content-Type: application/json; charset=UTF-8" -H "X-Upload-Content-Type: video/mp4" -H "X-Upload-Content-Length: $TOTAL" --data-binary @"$META"
URL=$(grep -i '^location' $T/h | sed 's/^[Ll]ocation: //' | tr -d '\r'); [ -n "$URL" ] || { echo "falha ao iniciar (401 = token expirado):"; cat $T/i; exit 1; }
CH=$((256*1024*1024)); off=0
while [ $off -lt $TOTAL ]; do
  end=$((off+CH-1)); [ $end -ge $TOTAL ] && end=$((TOTAL-1)); len=$((end-off+1))
  code=$(tail -c +$((off+1)) "$F" | head -c $len | curl -sS -m 1800 -o $T/r -w "%{http_code}" -X PUT "$URL" -H "Content-Type: video/mp4" -H "Content-Length: $len" -H "Content-Range: bytes $off-$end/$TOTAL" --data-binary @-)
  echo "bytes $off-$end -> $code"
  case $code in 308) off=$((end+1));; 200|201) break;; *) echo "ERRO $code"; head -c 400 $T/r; exit 1;; esac
done
ID=$(python3 -c "import json;print(json.load(open('$T/r'))['id'])"); echo "VIDEO: https://studio.youtube.com/video/$ID/edit"
[ -n "$THUMB" ] && curl -sS -m 60 -X POST "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=$ID&uploadType=media" -H "Content-Type: image/jpeg" --data-binary @"$THUMB" | head -c 150

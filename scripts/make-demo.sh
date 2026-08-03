#!/usr/bin/env bash
# הרכבת סרטון דמו 9:16 מהקליפים בתיקיית clips/
# שימוש:  ./scripts/make-demo.sh [--no-title] [--music path/to/music.mp3]
# פלט:    demo-batya-claud.mp4
#
# דרישות: ffmpeg. לכותרת עברית תקינה נדרש ffmpeg עם libharfbuzz/fribidi
# (בדיקה: ffmpeg -filters | grep drawtext). אם הטקסט יוצא הפוך — להריץ עם --no-title
# ולהוסיף את הכותרת בקאפקאט.

set -euo pipefail
cd "$(dirname "$0")/.."

TITLE="בתיה וקלוד • עין הוד"
OUT="demo-batya-claud.mp4"
CLIP_LEN=5          # שניות לכל קליפ
XFADE=0.5           # אורך מעבר
W=1080; H=1920
NO_TITLE=0
MUSIC=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-title) NO_TITLE=1; shift ;;
    --music) MUSIC="$2"; shift 2 ;;
    *) echo "אופציה לא מוכרת: $1"; exit 1 ;;
  esac
done

shopt -s nullglob
CLIPS=(clips/*.mp4 clips/*.mov clips/*.webm)
N=${#CLIPS[@]}
if (( N < 2 )); then
  echo "צריך לפחות 2 קליפים בתיקיית clips/ (נמצאו: $N)"; exit 1
fi
echo "נמצאו $N קליפים:"; printf '  %s\n' "${CLIPS[@]}"

# פונט עם תמיכה בעברית
FONT=""
for f in /usr/share/fonts/truetype/noto/NotoSansHebrew-Bold.ttf \
         /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf \
         /System/Library/Fonts/Supplemental/Arial\ Hebrew.ttc \
         "C:/Windows/Fonts/arialbd.ttf"; do
  [[ -f "$f" ]] && FONT="$f" && break
done
if [[ -z "$FONT" && $NO_TITLE -eq 0 ]]; then
  echo "אזהרה: לא נמצא פונט עברי — ממשיך בלי כותרת (הוסף בקאפקאט)"
  NO_TITLE=1
fi

# בניית פילטר: נרמול כל קליפ ל-1080x1920, ואז שרשור עם xfade
FILTER=""
INPUTS=()
for i in "${!CLIPS[@]}"; do
  INPUTS+=(-i "${CLIPS[$i]}")
  FILTER+="[$i:v]trim=duration=${CLIP_LEN},setpts=PTS-STARTPTS,scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H},fps=30,format=yuv420p[v$i];"
done

PREV="v0"
OFFSET=$(( CLIP_LEN ))
for (( i=1; i<N; i++ )); do
  CUR="x$i"
  OFF=$(echo "$i * ($CLIP_LEN - $XFADE)" | bc)
  FILTER+="[$PREV][v$i]xfade=transition=fade:duration=${XFADE}:offset=${OFF}[$CUR];"
  PREV="$CUR"
done

if [[ $NO_TITLE -eq 0 ]]; then
  # כותרת ב-3 השניות הראשונות. אם היא יוצאת הפוכה (RTL) — להריץ עם --no-title ולדווח.
  FILTER+="[$PREV]drawtext=fontfile='${FONT}':text='${TITLE}':fontcolor=white:fontsize=72:box=1:boxcolor=black@0.45:boxborderw=24:x=(w-text_w)/2:y=h*0.18:enable='lte(t,3)'[vout]"
else
  FILTER+="[$PREV]copy[vout]"
fi

AUDIO_ARGS=()
MAP_AUDIO=()
if [[ -n "$MUSIC" ]]; then
  AUDIO_ARGS=(-i "$MUSIC")
  MAP_AUDIO=(-map "${N}:a" -shortest -c:a aac -b:a 128k)
  echo "מוזיקה: $MUSIC"
else
  echo "בלי מוזיקה (תתווסף בקאפקאט)"
fi

ffmpeg -y "${INPUTS[@]}" "${AUDIO_ARGS[@]}" \
  -filter_complex "$FILTER" \
  -map "[vout]" "${MAP_AUDIO[@]}" \
  -c:v libx264 -preset medium -crf 20 -movflags +faststart \
  -t 30 "$OUT"

echo ""
echo "נוצר: $OUT"
echo "לבדוק: (1) אורך 25-30 שניות (2) כותרת קריאה ולא הפוכה (3) מעברים חלקים"
echo "אם הכותרת הפוכה — להריץ שוב עם --no-title ולהוסיף טקסט בקאפקאט"

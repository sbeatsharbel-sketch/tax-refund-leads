# clips/ — קליפים מונפשים מ-OpenArt

**⚠️ שלב זה רץ רק בדפדפן שלך** (חשבון OpenArt מחובר בפרופיל העסקי) — לא בסביבת הענן.

## תהליך (לכל אחת מ-5 התמונות החזקות ב-photos/)

1. פתח את OpenArt בפרופיל הכרום העסקי → Image to Video.
2. העלה תמונה, בחר משך 5 שניות, יחס 9:16 אם קיים.
3. פרומפטים:

**חוץ/נוף:**
```
Gentle breeze moving the plants, soft warm sunlight, curtains swaying slightly, slow cinematic camera push-in, peaceful atmosphere
```

**פנים:**
```
Dust particles floating in a sunbeam, curtain moving gently, slow cinematic camera pan, cozy warm light
```

4. הורד כל קליפ לתיקייה הזו בשם תואם לתמונה: `01-exterior.mp4` וכו'.
5. בדוק כל קליפ מול הצ'קליסט: אין "המסה" של קווים ישרים, מים/עלים זזים טבעי, אין עיוותים.

## אחרי שיש 5 קליפים
```
./scripts/make-demo.sh
```
יוצר את `demo-batya-claud.mp4` (9:16, עד 30 שניות, כותרת פתיחה + מעברים).
אם הכותרת העברית יוצאת הפוכה: `./scripts/make-demo.sh --no-title` והוסף טקסט בקאפקאט.
מוזיקה (אופציונלי): `./scripts/make-demo.sh --music path/to/track.mp3`

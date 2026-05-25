# README — חיבור Webhook אמיתי מ-Make

---

## ⚠️ חובה לבצע לפני העלאת האתר לאוויר

קובץ `index.html` מכיל כתובת Webhook דמה:

```
https://hook.eu1.make.com/YOUR_WEBHOOK_ID
```

**אם לא תחליפו אותה בכתובת אמיתית — הלידים לא יישמרו ולא תקבלו שום התראה.**

---

## שלב 1: פתיחת Scenario חדש ב-Make

1. היכנסו לחשבון Make שלכם בכתובת [https://make.com](https://make.com).
2. לחצו על **"Create a new scenario"** (כפתור כחול בפינה הימנית העליונה).
3. לחצו על סימן **"+"** להוספת מודול ראשון.
4. חפשו **"Webhooks"** ובחרו **"Custom webhook"**.
5. לחצו **"Add"** ואז **"Save"**.
6. Make ייצור לכם כתובת Webhook ייחודית — לדוגמה:
   ```
   https://hook.eu1.make.com/abc123xyz456
   ```
7. **העתיקו את הכתובת הזאת.**

---

## שלב 2: הדבקת ה-URL בקובץ index.html

1. פתחו את קובץ `index.html` בעורך טקסט (Notepad++, VS Code, וכו').
2. חפשו את השורה הבאה (שורה ~833):
   ```javascript
   const WEBHOOK_URL = 'https://hook.eu1.make.com/YOUR_WEBHOOK_ID';
   ```
3. החליפו את `YOUR_WEBHOOK_ID` בחלק האמיתי מהכתובת שהעתקתם.
   לדוגמה:
   ```javascript
   const WEBHOOK_URL = 'https://hook.eu1.make.com/abc123xyz456';
   ```
4. שמרו את הקובץ.

---

## שלב 3: הוספת פעולות ל-Scenario ב-Make

לאחר שה-Webhook מקבל נתונים, הוסיפו מודולים לפי הצורך:

| מה לעשות | מודול ב-Make |
|----------|-------------|
| שמירת ליד ב-Google Sheets | Google Sheets → Add a Row |
| שליחת הודעת וואטסאפ | WhatsApp Business → Send a Message |
| שליחת מייל התראה | Gmail / Email → Send an Email |
| שמירה ב-CRM | HubSpot / Pipedrive → Create a Contact |

---

## שלב 4: בדיקה

1. לאחר שהדבקתם את ה-URL האמיתי, העלו את `index.html` לשרת.
2. מלאו את הטופס עם פרטי בדיקה.
3. ב-Make, לחצו **"Run once"** ובדקו שהנתונים הגיעו ל-Scenario.
4. אם הנתונים הגיעו — הכל עובד. אם לא — בדקו שה-URL נכון.

---

## מה קורה אם ה-Webhook נכשל?

- המשתמש **לא** יועבר לעמוד התודה.
- יוצגת הודעת שגיאה אדומה בטופס.
- כפתור השליחה יחזור למצב רגיל.
- **לא תירשם המרה** ב-Google Ads או ב-Meta Pixel.
- המשתמש יכול לנסות שוב.

---

## קבצים בחבילה זו

| קובץ | תיאור |
|------|-------|
| `index.html` | דף הנחיתה המלא |
| `thank-you.html` | עמוד תודה לאחר שליחה מוצלחת |
| `README.md` | הוראות חיבור (קובץ זה) |

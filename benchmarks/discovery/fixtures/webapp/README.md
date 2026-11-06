# Acme Portal

Customer portal prototype.

```bash
npm start        # http://127.0.0.1:{{PORT}} (set PORT to change)
npm test
```

Demo account: `demo` / `demo123`. The session is created by `POST /login`
and stored in a cookie. Outside production, `GET /dev/login` signs in as the
demo user directly. No database: sessions live in memory.

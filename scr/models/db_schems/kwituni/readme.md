## Run Alembic Migrations

### Configuration



```bash
cp scr/models/db_schems/kwituni/alembic.ini.example scr/models/db_schems/kwituni/alembic.ini
```
- update the `almbic.ini` with your database credentials (`sqlalchemy.url`)


```bash
alembic -c scr/models/db_schems/kwituni/alembic.ini upgrade head
```

```bash
alembic -c scr/models/db_schems/kwituni/alembic.ini revision --autogenerate -m "create tables"
```
```bash
alembic -c scr/models/db_schems/kwituni/alembic.ini upgrade head
```

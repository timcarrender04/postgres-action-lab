# How to prompt and plan this build

This lab is one Postgres table and four HTTP verbs. The page is the table. A click is the action. The strip above the grid is the reaction: status, SQL, and the row that appeared, changed, or disappeared.

Plan that before any file is written. The prompts below are the three turns that produced this folder. Each one adds a constraint. None of them names a framework tour or a second app.

## 1. Name the folder and the picture

Say where the lab lives, and what a person in the room should see.

> okay lets agentic-coding/Phase 2/Week 5/Postgress_Lab
>
> the goal is that we can walk through and understand postgres and show in real time GET, POST, PUT and DELETE but in view of a table and action to reaction

That prompt fixes four things:

- The path. The folder name stays `Postgress_Lab`, including the spelling.
- The subject. Postgres, not a tour of FastAPI features.
- The four verbs. GET, POST, PUT, and DELETE. PUT is in this lab even though the Week 3 gate stops at POST and DELETE.
- The picture. One table on screen. An action, then the reaction in that same table.

Week 5's class notes are still Git. This folder is only the Postgres walkthrough. Say that in the plan so the lab does not get mixed into the Git deck.

## 2. Put the teaching in the code

The second prompt is one sentence. It changes where the explanation lives.

> ensure we have notes and comments so students can understand what is happening in code

Ask for comments that explain the Postgres idea, not comments that restate the syntax. Each file a student opens gets a note at the top and a note on every block they will be asked about.

On the page, each verb gets one line they can read before they click:

- GET reads one row. The table does not change.
- POST adds a row. Postgres assigns the id.
- PUT replaces name and price on a row that already exists.
- DELETE removes that row. The next delete of the same id finds nothing.

The reaction strip keeps the last SQL on screen so they can match it to the comment in `main.py`.

## 3. Approve the plan, then build

The third prompt is the go-ahead. Do not start the files while the plan is still open.

> Implement the plan as specified. Do not edit the plan file itself.

A plan that is still being edited and a folder full of code will drift apart. Lock the plan, then write the files to match it.

## What the plan has to decide

Write these down before Compose, before a model, before a route.

**One table.** `items`, with `id`, `name`, `price`, and `updated_at`. Three seed rows so GET, PUT, and DELETE have something to touch the moment the page loads. Seed only when the table is empty. The `pgdata` volume is why a restart keeps the rows.

**The grid is a SELECT.** Every paint runs `SELECT id, name, price, updated_at FROM items ORDER BY id`. The buttons are the only way a row gets in, changes, or leaves.

**Status codes from the course.** GET is 200 or 404. POST is 201. PUT is 200 or 404. DELETE is 204 or 404. A 204 has no body. A second DELETE of the same id is 404, and that DELETE does not run. A price that is not a number is 422, and Postgres is not asked to write.

**The same stack as Week 3.** Postgres 16, FastAPI, SQLAlchemy, `psycopg2`. Database host `db`. User `postgres`, password `devpass`, database `appdb`. Port 5432 stays published so this command shows the same rows as the page:

```bash
docker compose exec db psql -U postgres -d appdb -c "SELECT * FROM items;"
```

**Files, and nothing past them.**

- `docker-compose.yml` — `api` and `db`, healthcheck, volume `pgdata`. Comment why the host is `db`, why `localhost` inside the API container is the API itself, what the healthcheck waits for, and why 5432 is published.
- `Dockerfile` and `requirements.txt` — the API image. Bind `0.0.0.0` so the laptop can open the port.
- `database.py` — engine, session, `get_db`. Comment engine versus session, why the session closes, and why `create_all` runs only after the model is imported.
- `models.py` — `Item`. Comment that Postgres fills `id`, the request fills `name` and `price`, and `updated_at` moves only on a write.
- `main.py` — the four routes, the seed, and the page. One comment block per verb: the SQL, the status, and `commit` then `refresh` on POST so the JSON includes the id Postgres just assigned.

**Walk the room in this order.**

1. Load the page. Read the three seed rows. Say the grid is a SELECT.
2. GET an id that exists, then one that does not. The table does not change. Status goes 200, then 404.
3. POST a name and a price. The strip shows INSERT. The new row appears with a real id.
4. PUT that id. The strip shows UPDATE. Only that row's name, price, and `updated_at` change.
5. DELETE that id. The strip shows DELETE and 204. The row is gone. DELETE the same id again. The table stays put and the status is 404.

## After it runs

Open the page and click the four verbs in that order. Then run the `psql` command and read the same rows. The highlighted row on the page and the row in `psql` are one row.

The file publishes port 8000. On a machine where 8000 is already taken, start with:

```bash
API_PORT=8035 docker compose up --build
```

The API inside the container is still port 8000. Only the laptop port changes.

"""
One Postgres table, four HTTP verbs, and the row that changed.

The grid on http://localhost:8000 is SELECT * FROM items.
Each button runs one verb. The strip shows the status, the SQL,
and what happened to the row.

GET reads. POST inserts. PUT updates. DELETE removes.
A missing id is 404 and does not write.

The same routes are at http://localhost:8000/docs.
"""

import html
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db

# This import registers the items table on Base. create_all only
# creates models that have already been imported. Leave it above
# prepare_database. Without it, the page fails with
# "relation items does not exist".
from models import Item

# Statements the strip shows. These are the statements the route runs.
# SQLAlchemy sends the values separately, as bound parameters.
SQL_LIST = "SELECT id, name, price, updated_at FROM items ORDER BY id"
SQL_GET = "SELECT id, name, price, updated_at FROM items WHERE id = :id"
SQL_INSERT = "INSERT INTO items (name, price) VALUES (:name, :price) RETURNING id"
SQL_UPDATE = "UPDATE items SET name = :name, price = :price, updated_at = now() WHERE id = :id"
SQL_DELETE = "DELETE FROM items WHERE id = :id"


class ItemIn(BaseModel):
    """The JSON body for POST and PUT.

    FastAPI checks this before the route runs. A missing price, or a
    price that is not a number, is 422. That rejection happens here.
    Postgres is not asked to write.
    """

    name: str = Field(min_length=1)
    price: float


def prepare_database() -> None:
    """Create the table, then seed it if it is empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


def seed(db: Session) -> None:
    """Three rows so the first GET, PUT, and DELETE have something to touch.

    This runs only when the table is empty. Rows live in the pgdata
    volume, so a restart keeps what the room already wrote.
    """
    if db.query(Item).count():
        return
    db.add_all(
        [
            Item(name="Real Apple", price=0.50),
            Item(name="Notebook", price=3.00),
            Item(name="Marker", price=1.25),
        ]
    )
    db.commit()


def all_items(db: Session) -> list[Item]:
    """The page grid. This SELECT does not change a row."""
    return db.query(Item).order_by(Item.id).all()


def find_item(db: Session, item_id: int) -> Item | None:
    """Look up one row. None means the id is not in the table."""
    return db.query(Item).filter(Item.id == item_id).first()


def format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def item_dict(row: Item) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "price": row.price,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def respond(
    status: int,
    sql: str,
    effect: str,
    body: dict | None = None,
    row_id: int | None = None,
):
    """JSON for curl, headers for the page.

    DELETE returns 204, which has no body. The page still needs the SQL
    and the sentence, so those travel on headers for every verb.
    """
    headers = {"X-SQL": sql, "X-Effect": effect, "Cache-Control": "no-store"}
    if row_id is not None:
        headers["X-Row-Id"] = str(row_id)
    if status == 204:
        return Response(status_code=204, headers=headers)
    return JSONResponse(status_code=status, content=body if body is not None else {}, headers=headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    prepare_database()
    yield


app = FastAPI(title="Items table", lifespan=lifespan)


@app.get("/items")
def list_items(db: Session = Depends(get_db)):
    """The grid. SELECT every row. This route does not write.

    Cache-Control is no-store so a deleted row cannot linger in the
    browser as a cached copy of this list.
    """
    rows = all_items(db)
    return JSONResponse(
        content=[item_dict(row) for row in rows],
        headers={"X-SQL": SQL_LIST, "Cache-Control": "no-store"},
    )


@app.get("/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    """GET is a SELECT. It does not write.

    A missing id is 404. The table does not gain or lose a row,
    and updated_at stays where it was.
    """
    row = find_item(db, item_id)
    if row is None:
        return respond(
            404,
            SQL_GET,
            f"No row with id {item_id}. The table did not change.",
            {"detail": "Item not found"},
        )
    return respond(
        200,
        SQL_GET,
        f"Read row {row.id}. The table did not change.",
        item_dict(row),
        row_id=row.id,
    )


@app.post("/items")
def create_item(body: ItemIn, db: Session = Depends(get_db)):
    """POST is an INSERT, then commit, then refresh.

    commit writes the row. refresh copies the id Postgres just assigned
    back onto the object. Skip refresh and the JSON says id: null while
    the row is already visible in psql. Status 201 means the row was created.

    A price that is not a number never reaches this function. FastAPI
    answers 422 first, and Postgres is not asked to write.
    """
    row = Item(name=body.name, price=body.price)
    db.add(row)
    db.commit()
    db.refresh(row)
    return respond(
        201,
        SQL_INSERT,
        f"Inserted row {row.id}. Postgres assigned the id.",
        item_dict(row),
        row_id=row.id,
    )


@app.put("/items/{item_id}")
def update_item(item_id: int, body: ItemIn, db: Session = Depends(get_db)):
    """PUT is an UPDATE of a row that already exists.

    The body replaces name and price. It is not a patch of one field.
    updated_at moves because this write sends now(). A missing id is 404,
    and the UPDATE does not run. Status 200 means the row was written.
    """
    row = find_item(db, item_id)
    if row is None:
        return respond(
            404,
            SQL_GET,
            f"No row with id {item_id}. The UPDATE did not run.",
            {"detail": "Item not found"},
        )
    row.name = body.name
    row.price = body.price
    db.commit()
    # refresh loads the new updated_at. Without it the page can still
    # show the timestamp from before this write.
    db.refresh(row)
    return respond(
        200,
        SQL_UPDATE,
        f"Updated row {row.id}. name, price, and updated_at changed.",
        item_dict(row),
        row_id=row.id,
    )


@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """DELETE removes the row. Status 204 has no body.

    A second delete of the same id finds nothing. The DELETE does not
    run, and the answer is 404. The table stays as it is.
    """
    row = find_item(db, item_id)
    if row is None:
        return respond(
            404,
            SQL_GET,
            f"No row with id {item_id}. The DELETE did not run.",
            {"detail": "Item not found"},
        )
    db.delete(row)
    db.commit()
    return respond(204, SQL_DELETE, f"Deleted row {item_id}.")


def render_row(row: Item) -> str:
    return (
        f'<tr data-id="{row.id}">'
        f"<td>{row.id}</td>"
        f"<td>{html.escape(row.name)}</td>"
        f"<td>{row.price:.2f}</td>"
        f"<td>{html.escape(format_time(row.updated_at))}</td>"
        "</tr>"
    )


def render_rows(rows: list[Item]) -> str:
    if not rows:
        return '<tr><td colspan="4">The table is empty. POST a row.</td></tr>'
    return "".join(render_row(row) for row in rows)


@app.get("/", response_class=HTMLResponse)
def home(db: Session = Depends(get_db)):
    """First paint of the grid. Same SELECT the buttons refresh from."""
    page = PAGE.replace("__ROWS__", render_rows(all_items(db)))
    page = page.replace("__SQL_LIST__", html.escape(SQL_LIST))
    return HTMLResponse(page)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Items — action and reaction</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0d1c2e;
      --card: #1a2642;
      --text: #f2f3fa;
      --muted: #c5c6d0;
      --line: #31405f;
      --gold: #c9a961;
      --blue: #1a5dab;
      --ok: #8fd19a;
      --gone: #e7d7a8;
      --missing: #f0a8a2;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 18px/1.45 system-ui, sans-serif;
    }
    main { max-width: 1280px; margin: 0 auto; padding: 28px 24px 48px; }
    h1 { margin: 0 0 8px; font-size: 32px; letter-spacing: 0.02em; }
    .lede { margin: 0 0 20px; color: var(--muted); max-width: 70ch; }
    code { font-family: ui-monospace, monospace; color: var(--gold); }
    #reaction {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 22px;
    }
    #reaction article, form {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px 16px;
    }
    .label {
      margin: 0 0 6px;
      color: var(--gold);
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    #reaction p:last-child { margin: 0; word-break: break-word; }
    #reaction-sql { font-family: ui-monospace, monospace; font-size: 15px; }
    #reaction-status.ok { color: var(--ok); }
    #reaction-status.gone { color: var(--gone); }
    #reaction-status.missing { color: var(--missing); }
    table { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
    caption {
      caption-side: bottom;
      text-align: left;
      color: var(--muted);
      padding-top: 10px;
      font-size: 16px;
    }
    th, td { text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--line); }
    th { color: var(--gold); font-weight: 600; }
    td { font-variant-numeric: tabular-nums; }
    tr.hit td { background: #16365f; box-shadow: inset 4px 0 0 var(--gold); }
    .terminal { color: var(--muted); font-size: 16px; margin: 0 0 22px; }
    .actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    form h2 { margin: 0 0 8px; font-size: 22px; }
    label { display: block; margin: 10px 0 4px; color: var(--muted); font-size: 15px; }
    input {
      width: 100%;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #0d1c2e;
      color: var(--text);
      font: inherit;
    }
    button {
      margin-top: 14px;
      width: 100%;
      padding: 12px 14px;
      border: 0;
      border-radius: 8px;
      background: var(--blue);
      color: white;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }
    button:disabled { opacity: 0.6; cursor: wait; }
    .note { margin: 12px 0 0; color: var(--muted); font-size: 16px; }
    noscript { display: block; margin-bottom: 16px; color: var(--missing); }
    @media (max-width: 800px) {
      #reaction, .actions { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <h1>items</h1>
    <p class="lede">This grid is <code>__SQL_LIST__</code>. Postgres is the list. A button is the only way a row gets in, changes, or leaves.</p>
    <noscript>The buttons send GET, POST, PUT, and DELETE from this page. Enable JavaScript, or call those routes with curl.</noscript>
    <section id="reaction" aria-live="polite">
      <article>
        <p class="label">Action</p>
        <p id="reaction-verb">Waiting</p>
      </article>
      <article>
        <p class="label">Status</p>
        <p id="reaction-status">—</p>
      </article>
      <article>
        <p class="label">SQL</p>
        <p id="reaction-sql">__SQL_LIST__</p>
      </article>
      <article>
        <p class="label">Reaction</p>
        <p id="reaction-effect">The grid is this SELECT. Nothing has been written yet.</p>
      </article>
    </section>
    <table>
      <thead>
        <tr><th>id</th><th>name</th><th>price</th><th>updated_at</th></tr>
      </thead>
      <tbody id="rows">__ROWS__</tbody>
      <caption>id comes from Postgres. name and price come from POST and PUT. updated_at changes only when a row is written.</caption>
    </table>
    <p class="terminal">Same rows from the shell: <code>docker compose exec db psql -U postgres -d appdb -c "SELECT * FROM items;"</code></p>
    <section class="actions">
      <form data-verb="GET" data-url="/items/{id}">
        <h2>GET</h2>
        <label for="get-id">id</label>
        <input id="get-id" name="item_id" type="number" min="1" step="1" required>
        <button type="submit">GET</button>
        <p class="note">Reads one row. The table does not change.</p>
      </form>
      <form data-verb="POST" data-url="/items">
        <h2>POST</h2>
        <label for="post-name">name</label>
        <input id="post-name" name="name" required>
        <label for="post-price">price</label>
        <input id="post-price" name="price" type="number" step="0.01" required>
        <button type="submit">POST</button>
        <p class="note">Adds a row. Postgres assigns the id.</p>
      </form>
      <form data-verb="PUT" data-url="/items/{id}">
        <h2>PUT</h2>
        <label for="put-id">id</label>
        <input id="put-id" name="item_id" type="number" min="1" step="1" required>
        <label for="put-name">name</label>
        <input id="put-name" name="name" required>
        <label for="put-price">price</label>
        <input id="put-price" name="price" type="number" step="0.01" required>
        <button type="submit">PUT</button>
        <p class="note">Replaces name and price on a row that already exists.</p>
      </form>
      <form data-verb="DELETE" data-url="/items/{id}">
        <h2>DELETE</h2>
        <label for="delete-id">id</label>
        <input id="delete-id" name="item_id" type="number" min="1" step="1" required>
        <button type="submit">DELETE</button>
        <p class="note">Removes that row. The next delete of the same id finds nothing.</p>
      </form>
    </section>
  </main>
  <script>
    const statusLabel = {
      200: "200 OK",
      201: "201 Created",
      204: "204 No Content",
      404: "404 Not Found",
      422: "422 Unprocessable Entity"
    };

    function statusClass(code) {
      if (code === 200 || code === 201) return "ok";
      if (code === 204) return "gone";
      if (code === 404 || code === 422) return "missing";
      return "";
    }

    function formatTime(value) {
      if (!value) return "";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toISOString().replace("T", " ").slice(0, 19) + " UTC";
    }

    function paintRows(rows, highlightId) {
      const tbody = document.querySelector("#rows");
      tbody.replaceChildren();
      if (!rows.length) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 4;
        td.textContent = "The table is empty. POST a row.";
        tr.append(td);
        tbody.append(tr);
        return;
      }
      for (const row of rows) {
        const tr = document.createElement("tr");
        tr.dataset.id = String(row.id);
        if (highlightId && String(row.id) === String(highlightId)) tr.className = "hit";
        const cells = [row.id, row.name, Number(row.price).toFixed(2), formatTime(row.updated_at)];
        for (const value of cells) {
          const td = document.createElement("td");
          td.textContent = value;
          tr.append(td);
        }
        tbody.append(tr);
      }
    }

    // The grid is always a fresh SELECT. no-store skips a cached copy,
    // which would still show a row that DELETE already removed.
    async function loadTable(highlightId) {
      const res = await fetch("/items", { cache: "no-store" });
      paintRows(await res.json(), highlightId);
    }

    function showReaction(verbPath, statusCode, sql, effect) {
      document.querySelector("#reaction-verb").textContent = verbPath;
      const status = document.querySelector("#reaction-status");
      status.textContent = statusLabel[statusCode] || String(statusCode);
      status.className = statusClass(statusCode);
      document.querySelector("#reaction-sql").textContent = sql || "";
      document.querySelector("#reaction-effect").textContent = effect;
    }

    document.querySelectorAll("form").forEach((form) => {
      form.addEventListener("submit", async (event) => {
        // The form does not navigate. The fetch below sends the real verb.
        event.preventDefault();
        const button = form.querySelector("button");
        const verb = form.dataset.verb;
        const data = new FormData(form);
        let url = form.dataset.url;
        if (url.includes("{id}")) url = url.replace("{id}", data.get("item_id"));
        let payload = null;
        if (verb === "POST" || verb === "PUT") {
          payload = JSON.stringify({ name: data.get("name"), price: Number(data.get("price")) });
        }
        button.disabled = true;
        try {
          const res = await fetch(url, {
            method: verb,
            cache: "no-store",
            headers: payload ? { "Content-Type": "application/json" } : undefined,
            body: payload
          });
          // 204 has no body. The SQL and the sentence are the headers
          // set beside the route in main.py.
          let effect = res.headers.get("X-Effect");
          if (!effect && res.status === 422) {
            effect = "The body was the wrong shape. This route never ran, so Postgres did not change.";
          }
          if (!effect) effect = "The request finished.";
          await loadTable(res.headers.get("X-Row-Id"));
          showReaction(verb + " " + url, res.status, res.headers.get("X-SQL"), effect);
          const hit = document.querySelector("tr.hit");
          if (hit) hit.scrollIntoView({ block: "nearest" });
        } catch (error) {
          showReaction(verb + " " + url, 0, "", "The API did not answer.");
        } finally {
          button.disabled = false;
        }
      });
    });
  </script>
</body>
</html>
"""

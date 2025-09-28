import asyncpg
import os
import json
import uuid
from datetime import datetime,UTC
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def create_pool():
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return pool


async def create_tables(pool):
    create_pages = """
    CREATE TABLE IF NOT EXISTS pages (
      page_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      url TEXT UNIQUE NOT NULL,
      scraped_at TIMESTAMPTZ DEFAULT now(),
      title TEXT,
      meta_description TEXT,
      canonical_url TEXT,
      category TEXT,
      priority INT,
      tags TEXT[],
      checksum TEXT,
      etag TEXT,
      last_modified_at TEXT,
      content_type TEXT,
      http_status TEXT,        
      is_active BOOLEAN DEFAULT TRUE,
      first_seen TIMESTAMPTZ DEFAULT now(),
      last_scraped_at TIMESTAMPTZ,
      current_version_id UUID,
      last_updated_at TIMESTAMPTZ,
      cleaned_content TEXT,
      content_md TEXT,
      is_vectorized BOOLEAN DEFAULT FALSE
    );
    CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
    """
    # CREATE INDEX IF NOT EXISTS idx_pages_vectorize_status ON pages(is_vectorized, is_active);


    create_versions = """
    CREATE TABLE IF NOT EXISTS page_versions (
      id UUID PRIMARY KEY,
      page_id UUID REFERENCES pages(page_id) ON DELETE CASCADE,
      scraped_at TIMESTAMPTZ DEFAULT now(),
      content TEXT,
      checksum TEXT,
      etag TEXT,
      last_modified TEXT,
      metadata JSONB,
      is_current BOOLEAN DEFAULT TRUE
    );
    CREATE INDEX IF NOT EXISTS idx_versions_page_id ON page_versions(page_id);
    """

    async with pool.acquire() as conn:
        await conn.execute(create_pages)
        await conn.execute(create_versions)


async def get_page_by_url(conn, url: str):
    return await conn.fetchrow("SELECT page_id, current_version_id FROM pages WHERE url = $1", url)


async def get_version_by_id(conn, version_id):
    return await conn.fetchrow("SELECT id, checksum FROM page_versions WHERE id = $1", version_id)


async def upsert_page(pool, url: str, metadata: dict, content_md: str, raw_html: str | None, llm_raw: str | None, llm_cleaned: str | None):
    """
    Upsert logic:
      - If page doesn't exist: create page + page_version and set current_version_id.
      - If exists: compare checksum with current version:
          - If changed: create new page_version, mark old is_current=false, update pages.current_version_id + last_updated_at
          - If unchanged: only update last_scraped_at and category/priority/llm_raw (not last_updated_at).
    """

    page_id = None
    version_id = None

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await get_page_by_url(conn, url)

            # Case 1: New Page
            if row is None:
                page_id = uuid.uuid4()
                version_id = uuid.uuid4()

                await conn.execute(
                    """
                    INSERT INTO pages(
                        page_id, url, canonical_url, title, 
                        category, priority, tags, scraped_at, 
                        checksum, etag, last_modified_at, content_type, 
                        http_status, is_active, first_seen, last_scraped_at, 
                        meta_description, cleaned_content, content_md, current_version_id, last_updated_at
                    )
                    VALUES (
                        $1,$2,$3,$4,
                        $5,$6,$7,$8,
                        $9,$10,$11,$12,
                        $13,$14,$15,$16,
                        $17,$18,$19,$20,$21
                    )
                    """,
                    page_id,
                    url,
                    metadata.get("canonical_url"),
                    metadata.get("title"),
                    metadata.get("category"),
                    metadata.get("priority"),
                    metadata.get("tags"),
                    metadata.get("scraped_at"),
                    metadata.get("checksum"),
                    metadata.get("etag"),
                    metadata.get("last_modified_at"),
                    metadata.get("content_type"),
                    metadata.get("http_status"),
                    metadata.get("is_active", True),
                    metadata.get("first_seen") or datetime.now(UTC),
                    metadata.get("last_scraped_at") or datetime.now(UTC),
                    metadata.get("meta_description"),
                    llm_cleaned,
                    content_md,
                    version_id,                # ✅ link current version immediately
                    datetime.now(UTC)          # ✅ mark as latest content update
                )

                await conn.execute(
                    """
                    INSERT INTO page_versions(
                        id, page_id, scraped_at, content,
                        checksum, etag, last_modified, metadata, is_current
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,TRUE)
                    """,
                    version_id,
                    page_id,
                    metadata.get("scraped_at") or datetime.now(UTC),
                    content_md,
                    metadata.get("checksum"),
                    metadata.get("etag"),
                    metadata.get("last_modified_at"),
                    json.dumps(metadata, default=str)
                )

            else:
                # Case 2: Existing Page
                # page_id = row["id"] if "id" in row else row["page_id"]
                page_id = row["page_id"]
                current_version_id = row["current_version_id"]

                # get current checksum
                current_checksum = None
                if current_version_id:
                    cur = await get_version_by_id(conn, current_version_id)
                    if cur:
                        current_checksum = cur["checksum"]

                # Content Changed → New Version
                if metadata.get("checksum") != current_checksum:
                    # --- Changed content → new version ---
                    version_id = uuid.uuid4()

                    await conn.execute(
                        "UPDATE page_versions SET is_current = FALSE WHERE page_id = $1 AND is_current = TRUE",
                        page_id,
                    )

                    # Insert new version
                    await conn.execute(
                        """
                        INSERT INTO page_versions(
                            id, page_id, scraped_at, content,
                            checksum, etag, last_modified, metadata, is_current
                        )
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,TRUE)
                        """,
                        version_id,
                        page_id,
                        metadata.get("scraped_at") or datetime.now(UTC),
                        content_md,
                        metadata.get("checksum"),
                        metadata.get("etag"),
                        metadata.get("last_modified_at"),
                        json.dumps(metadata, default=str),
                    )

                    # Update pages table → mark new current version + last_updated_at
                    await conn.execute(
                        """
                        UPDATE pages
                        SET current_version_id = $1,
                            last_scraped_at = now(),
                            last_updated_at = now(),
                            canonical_url = $2,
                            title = $3, 
                            category = $4,
                            priority = $5,
                            content_md = $6
                        WHERE page_id = $7
                        """,
                        version_id,
                        metadata.get("canonical_url"),
                        metadata.get("title"),
                        metadata.get("category"),
                        metadata.get("priority"),
                        content_md,
                        page_id,
                    )
                else:
                    # No Change → Only update metadata
                    await conn.execute(
                        """
                        UPDATE pages
                        SET last_scraped_at = now(),
                            category = $1,
                            priority = $2,
                        WHERE page_id = $3
                        """,
                        metadata.get("category"),
                        metadata.get("priority"),
                        page_id,
                    )

    return {"page_id": str(page_id), "version_id": str(version_id) if version_id else None}

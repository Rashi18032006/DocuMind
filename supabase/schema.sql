-- DocuMind schema. Run once in the Supabase SQL editor.
create extension if not exists vector;

create table if not exists documents (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  pages       int,
  chunk_count int not null default 0,
  created_at  timestamptz not null default now()
);

create table if not exists chunks (
  id          bigserial primary key,
  document_id uuid not null references documents(id) on delete cascade,
  chunk_index int not null,
  page        int,
  content     text not null,
  embedding   vector(1536) not null  -- text-embedding-3-small
);

create index if not exists chunks_document_idx on chunks (document_id);

-- Approximate nearest-neighbour index for cosine distance (<=>).
create index if not exists chunks_embedding_idx
  on chunks using hnsw (embedding vector_cosine_ops);

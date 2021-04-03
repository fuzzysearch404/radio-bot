CREATE USER radiobot WITH PASSWORD 'verycoolmusic2021';

GRANT ALL PRIVILEGES ON DATABASE radiobotdata TO radiobot; 
GRANT ALL PRIVILEGES ON SCHEMA public to radiobot;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public to radiobot;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO radiobot;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO radiobot;

CREATE TABLE IF NOT EXISTS public.radio_stats(
    user_id bigint PRIMARY KEY,
    guild_id bigint NOT NULL,
    listening_minutes integer DEFAULT 0,
    song_requests integer DEFAULT 0,
    radio_stats_pkey PRIMARY KEY (user_id, guild_id)
);
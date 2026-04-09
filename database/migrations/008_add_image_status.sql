-- Migration 008: status de geração de imagem (pending / completed / failed)
ALTER TABLE generated_images
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'completed';

-- Torna campos opcionais para registros em estado pending
ALTER TABLE generated_images
    ALTER COLUMN minio_path DROP NOT NULL;

ALTER TABLE generated_images
    ALTER COLUMN prompt_used DROP NOT NULL;

ALTER TABLE generated_images
    ALTER COLUMN image_url DROP NOT NULL;

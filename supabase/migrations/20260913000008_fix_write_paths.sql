-- ============================================================
-- Migration 008: Align the schema with what the app actually writes
--
-- All changes are additive (new nullable/defaulted columns, new policies,
-- widened CHECK lists, deprecation flags/comments). Nothing is dropped
-- except one CHECK constraint that is immediately replaced by a wider one.
--
--   1. documents: columns the upload router writes and the UI reads.
--   2. Storage bucket `farm-documents` + per-user object policies.
--   3. field_activities: columns the activity log service writes.
--   4. csp_eligibility_assessments: allow act_now / pending_review.
--   5. weather_cache: UPDATE policy so the enrichment upsert can refresh rows.
--   6. Deprecate stale FY2025 CSP reference data (no deletes).
-- ============================================================

-- ------------------------------------------------------------
-- 1. documents
-- ------------------------------------------------------------
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS user_id     UUID REFERENCES public.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS file_name   TEXT,
    ADD COLUMN IF NOT EXISTS size_bytes  BIGINT,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at  TIMESTAMPTZ NOT NULL DEFAULT now();

-- Existing rows got now() from the default above; use their real upload time.
UPDATE public.documents
SET created_at = uploaded_at
WHERE uploaded_at IS NOT NULL
  AND created_at <> uploaded_at;

CREATE INDEX IF NOT EXISTS idx_documents_farm_created
    ON public.documents(farm_id, created_at DESC);

-- ------------------------------------------------------------
-- 2. Storage: private bucket, objects scoped to <user_id>/...
--    Upload path built in backend/app/routers/documents.py:
--    <user_id>/<farm_id>/<doc_type>/<uuid>_<file_name>
-- ------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public)
VALUES ('farm-documents', 'farm-documents', FALSE)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Users can upload own farm documents" ON storage.objects;
CREATE POLICY "Users can upload own farm documents"
    ON storage.objects FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'farm-documents'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

DROP POLICY IF EXISTS "Users can read own farm documents" ON storage.objects;
CREATE POLICY "Users can read own farm documents"
    ON storage.objects FOR SELECT TO authenticated
    USING (
        bucket_id = 'farm-documents'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

DROP POLICY IF EXISTS "Users can delete own farm documents" ON storage.objects;
CREATE POLICY "Users can delete own farm documents"
    ON storage.objects FOR DELETE TO authenticated
    USING (
        bucket_id = 'farm-documents'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

-- ------------------------------------------------------------
-- 3. field_activities
--    The API field `pest_disease_found` is stored in the existing
--    `pest_name` column (mapped in services/activity_log.py).
-- ------------------------------------------------------------
ALTER TABLE public.field_activities
    ADD COLUMN IF NOT EXISTS seed_treatment     TEXT,
    ADD COLUMN IF NOT EXISTS crop_year          INTEGER,
    ADD COLUMN IF NOT EXISTS tillage_depth_in   NUMERIC,
    ADD COLUMN IF NOT EXISTS cover_crop_species TEXT;  -- free text in the API (str), not text[]

-- ------------------------------------------------------------
-- 4. csp_eligibility_assessments.eligibility_status
--    Migration 003 declared the CHECK inline, so Postgres auto-named it
--    <table>_<column>_check.
-- ------------------------------------------------------------
ALTER TABLE public.csp_eligibility_assessments
    DROP CONSTRAINT IF EXISTS csp_eligibility_assessments_eligibility_status_check;

ALTER TABLE public.csp_eligibility_assessments
    ADD CONSTRAINT csp_eligibility_assessments_eligibility_status_check
    CHECK (eligibility_status IN (
        'act_now', 'eligible', 'pending_review',
        'not_eligible', 'not_evaluated', 'conditional'
    ));

-- ------------------------------------------------------------
-- 5. weather_cache: UPDATE policy (upsert needs INSERT + UPDATE)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update weather for own fields" ON public.weather_cache;
CREATE POLICY "Users can update weather for own fields"
    ON public.weather_cache FOR UPDATE
    USING (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    )
    WITH CHECK (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );

-- ------------------------------------------------------------
-- 6. Stale CSP reference data (not read by the app; kept for history)
--    Deadlines now live in backend/app/services/program_deadlines.py and
--    CSP limits in backend/app/services/program_rules.py.
-- ------------------------------------------------------------
UPDATE public.csp_application_deadlines
SET is_active = FALSE
WHERE fiscal_year <= 2025
  AND is_active = TRUE;

COMMENT ON TABLE public.csp_application_deadlines IS
    'Deprecated: seeded FY2025 dates, not used by the app. Source of truth is backend/app/services/program_deadlines.py.';

-- csp_state_payment_rates has no is_active column, so mark it with a comment.
COMMENT ON TABLE public.csp_state_payment_rates IS
    'Deprecated: FY2025 seed rows carry the retired $50,000 annual cap and are not used by the app. There is no CSP annual payment limitation in FY2026 (NB 440-26-2); see backend/app/services/program_rules.py.';

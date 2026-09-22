-- ============================================================
-- Migration 009: Add WITH CHECK to the user-scoped UPDATE policies
--
-- A Postgres UPDATE policy's USING clause is tested against the OLD row and
-- WITH CHECK against the NEW one. Nine policies from migrations 001, 002, 003
-- and 005 declare only USING, so a user who owns a row may UPDATE it to point
-- at a farm or field that belongs to somebody else — the row is re-parented
-- out of their own scope and disappears from their reads. Migration 008
-- already established the correct shape for weather_cache; this applies it to
-- every remaining UPDATE policy.
--
-- Additive and reversible: each policy is dropped and recreated under the same
-- name with the same USING predicate, plus the matching WITH CHECK. No schema,
-- data or access is removed, and no policy becomes more permissive.
--
--   1. users                        (own row)
--   2. farms                        (own row)
--   3. fields                       (farm ownership)
--   4. recommendations              (field -> farm ownership)
--   5. credit_eligibility           (farm ownership)
--   6. csp_eligibility_assessments  (farm ownership)
--   7. csp_farm_enhancements        (farm ownership)
--   8. field_activities             (field -> farm ownership)
--   9. yield_history                (field -> farm ownership)
--
-- tests/test_rls_policies.py fails if a future migration reintroduces an
-- UPDATE policy without WITH CHECK.
-- ============================================================

-- ------------------------------------------------------------
-- 1. users (migration 001)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own record" ON public.users;
CREATE POLICY "Users can update own record"
    ON public.users FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- ------------------------------------------------------------
-- 2. farms (migration 001)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own farms" ON public.farms;
CREATE POLICY "Users can update own farms"
    ON public.farms FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ------------------------------------------------------------
-- 3. fields (migration 001)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own fields" ON public.fields;
CREATE POLICY "Users can update own fields"
    ON public.fields FOR UPDATE
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()))
    WITH CHECK (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

-- ------------------------------------------------------------
-- 4. recommendations (migration 001)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own recommendation status" ON public.recommendations;
CREATE POLICY "Users can update own recommendation status"
    ON public.recommendations FOR UPDATE
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
-- 5. credit_eligibility (migration 002)
--    Upsert target of eqip.py and vcm.py, unique on (farm_id, program).
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own credit eligibility" ON public.credit_eligibility;
CREATE POLICY "Users can update own credit eligibility"
    ON public.credit_eligibility FOR UPDATE
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()))
    WITH CHECK (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

-- ------------------------------------------------------------
-- 6. csp_eligibility_assessments (migration 003)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own CSP eligibility assessments"
    ON public.csp_eligibility_assessments;
CREATE POLICY "Users can update own CSP eligibility assessments"
    ON public.csp_eligibility_assessments FOR UPDATE
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()))
    WITH CHECK (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

-- ------------------------------------------------------------
-- 7. csp_farm_enhancements (migration 003)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own CSP farm enhancements"
    ON public.csp_farm_enhancements;
CREATE POLICY "Users can update own CSP farm enhancements"
    ON public.csp_farm_enhancements FOR UPDATE
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()))
    WITH CHECK (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

-- ------------------------------------------------------------
-- 8. field_activities (migration 005)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own field activities"
    ON public.field_activities;
CREATE POLICY "Users can update own field activities"
    ON public.field_activities FOR UPDATE
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
-- 9. yield_history (migration 005)
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "Users can update own yield history"
    ON public.yield_history;
CREATE POLICY "Users can update own yield history"
    ON public.yield_history FOR UPDATE
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

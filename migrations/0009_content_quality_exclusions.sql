-- Allow the fixed-revision content-quality authority to record explicit
-- non-publication reasons without weakening the existing review/takedown set.

ALTER TABLE content.publication_exclusions_v2
    DROP CONSTRAINT IF EXISTS publication_exclusions_v2_reason_code_check;

ALTER TABLE content.publication_exclusions_v2
    ADD CONSTRAINT publication_exclusions_v2_reason_code_check CHECK (reason_code IN (
      'candidate_invalid', 'review_pending', 'review_review_required',
      'review_internal_only', 'review_blocked',
      'quality_non_result_capture', 'quality_prompt_output_mismatch',
      'quality_near_identical_cross_source_render', 'quality_exact_prompt_output_subset',
      'takedown_asset', 'takedown_asset_primary', 'takedown_prompt',
      'takedown_case', 'takedown_source'
    ));

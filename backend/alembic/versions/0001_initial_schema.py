from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=True),
    sa.Column('actor', sa.String(length=120), nullable=False),
    sa.Column('actor_role', sa.String(length=30), nullable=False),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('entity', sa.String(length=60), nullable=True),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('prev_hash', sa.String(length=64), nullable=False),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_created_at'), ['created_at'], unique=False)

    op.create_table('policies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=15), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('change_note', sa.Text(), nullable=True),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('policies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_policies_key'), ['key'], unique=False)
        batch_op.create_index(batch_op.f('ix_policies_status'), ['status'], unique=False)

    op.create_table('settings',
    sa.Column('key', sa.String(length=60), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=False),
    sa.Column('password_hash', sa.String(length=300), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('role', sa.String(length=30), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_role'), ['role'], unique=False)

    op.create_table('applications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=30), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('product', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('pending_stage', sa.String(length=30), nullable=True),
    sa.Column('loan_amount', sa.Float(), nullable=False),
    sa.Column('interest_rate', sa.Float(), nullable=False),
    sa.Column('tenure_months', sa.Integer(), nullable=False),
    sa.Column('purpose', sa.String(length=60), nullable=False),
    sa.Column('end_use', sa.String(length=60), nullable=True),
    sa.Column('policy_key', sa.String(length=30), nullable=False),
    sa.Column('property_type', sa.String(length=40), nullable=False),
    sa.Column('property_subtype', sa.String(length=30), nullable=False),
    sa.Column('property_city', sa.String(length=80), nullable=False),
    sa.Column('property_address', sa.String(length=300), nullable=False),
    sa.Column('property_pincode', sa.String(length=10), nullable=False),
    sa.Column('property_area_sqft', sa.Float(), nullable=False),
    sa.Column('locality_tier', sa.Integer(), nullable=False),
    sa.Column('survey_no', sa.String(length=60), nullable=False),
    sa.Column('declared_value', sa.Float(), nullable=False),
    sa.Column('seller_name', sa.String(length=200), nullable=True),
    sa.Column('owner_name', sa.String(length=200), nullable=True),
    sa.Column('existing_mortgage_amount', sa.Float(), nullable=False),
    sa.Column('under_construction', sa.Boolean(), nullable=False),
    sa.Column('consents', sa.JSON(), nullable=False),
    sa.Column('resolved_conflicts', sa.JSON(), nullable=False),
    sa.Column('stage_state', sa.JSON(), nullable=False),
    sa.Column('language', sa.String(length=5), nullable=False),
    sa.Column('submitted_at', sa.DateTime(), nullable=True),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_applications_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_applications_product'), ['product'], unique=False)
        batch_op.create_index(batch_op.f('ix_applications_reference'), ['reference'], unique=True)
        batch_op.create_index(batch_op.f('ix_applications_status'), ['status'], unique=False)

    op.create_table('applicants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('dob', sa.Date(), nullable=False),
    sa.Column('pan', sa.String(length=10), nullable=False),
    sa.Column('phone', sa.String(length=15), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=False),
    sa.Column('address', sa.String(length=300), nullable=False),
    sa.Column('city', sa.String(length=80), nullable=False),
    sa.Column('employment_type', sa.String(length=20), nullable=False),
    sa.Column('employer', sa.String(length=200), nullable=False),
    sa.Column('years_in_job', sa.Float(), nullable=False),
    sa.Column('monthly_income', sa.Float(), nullable=False),
    sa.Column('other_income', sa.Float(), nullable=False),
    sa.Column('existing_emi', sa.Float(), nullable=False),
    sa.Column('business_type', sa.String(length=30), nullable=True),
    sa.Column('annual_turnover', sa.Float(), nullable=True),
    sa.Column('annual_itr_income', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('applicants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_applicants_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_applicants_pan'), ['pan'], unique=False)

    op.create_table('assessments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('run', sa.Integer(), nullable=False),
    sa.Column('financial', sa.JSON(), nullable=False),
    sa.Column('risk', sa.JSON(), nullable=False),
    sa.Column('property_assessment', sa.JSON(), nullable=False),
    sa.Column('verification_summary', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assessments_application_id'), ['application_id'], unique=False)

    op.create_table('decisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('outcome', sa.String(length=10), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('decided_by', sa.String(length=120), nullable=False),
    sa.Column('policy_key', sa.String(length=30), nullable=False),
    sa.Column('policy_name', sa.String(length=60), nullable=False),
    sa.Column('policy_version', sa.Integer(), nullable=False),
    sa.Column('ruleset_version', sa.String(length=30), nullable=False),
    sa.Column('inputs', sa.JSON(), nullable=False),
    sa.Column('outputs', sa.JSON(), nullable=False),
    sa.Column('reason_codes', sa.JSON(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=False),
    sa.Column('evidence_refs', sa.JSON(), nullable=False),
    sa.Column('policy_snapshot', sa.JSON(), nullable=False),
    sa.Column('result_hash', sa.String(length=64), nullable=False),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('decisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_decisions_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_decisions_outcome'), ['outcome'], unique=False)

    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('channel', sa.String(length=10), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('delivery_status', sa.String(length=30), nullable=False),
    sa.Column('simulated', sa.Boolean(), nullable=False),
    sa.Column('recipient', sa.String(length=200), nullable=True),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)

    op.create_table('document_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('applicant_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('item_key', sa.String(length=80), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('due_at', sa.DateTime(), nullable=True),
    sa.Column('last_reminded_at', sa.DateTime(), nullable=True),
    sa.Column('reminders_sent', sa.Integer(), nullable=False),
    sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['applicant_id'], ['applicants.id'], ),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('document_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_requests_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_requests_status'), ['status'], unique=False)

    op.create_table('documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('applicant_id', sa.Integer(), nullable=True),
    sa.Column('doc_type', sa.String(length=40), nullable=False),
    sa.Column('detected_type', sa.String(length=40), nullable=True),
    sa.Column('original_name', sa.String(length=255), nullable=False),
    sa.Column('stored_path', sa.String(length=500), nullable=False),
    sa.Column('mime_type', sa.String(length=60), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('extraction_status', sa.String(length=30), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('text_excerpt', sa.Text(), nullable=True),
    sa.Column('findings', sa.JSON(), nullable=False),
    sa.Column('metadata_info', sa.JSON(), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=False),
    sa.Column('ocr_used', sa.Boolean(), nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.Column('uploaded_at', sa.DateTime(), nullable=False),
    sa.Column('superseded_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['applicant_id'], ['applicants.id'], ),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_doc_type'), ['doc_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_sha256'), ['sha256'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_status'), ['status'], unique=False)

    op.create_table('provider_calls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('applicant_id', sa.Integer(), nullable=True),
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('provider_name', sa.String(length=120), nullable=False),
    sa.Column('mode', sa.String(length=20), nullable=False),
    sa.Column('integration_status', sa.String(length=20), nullable=False),
    sa.Column('response_status', sa.String(length=20), nullable=False),
    sa.Column('consent_ref', sa.String(length=60), nullable=True),
    sa.Column('source_ref', sa.String(length=80), nullable=True),
    sa.Column('verification_result', sa.String(length=30), nullable=False),
    sa.Column('response', sa.JSON(), nullable=False),
    sa.Column('response_hash', sa.String(length=64), nullable=True),
    sa.Column('requested_at', sa.DateTime(), nullable=False),
    sa.Column('run', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['applicant_id'], ['applicants.id'], ),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('provider_calls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_provider_calls_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_provider_calls_provider'), ['provider'], unique=False)

    op.create_table('verification_checks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('applicant_id', sa.Integer(), nullable=True),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('disposition', sa.String(length=20), nullable=True),
    sa.Column('disposition_note', sa.Text(), nullable=True),
    sa.Column('disposition_by', sa.Integer(), nullable=True),
    sa.Column('run', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['applicant_id'], ['applicants.id'], ),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['disposition_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('verification_checks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_verification_checks_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_verification_checks_category'), ['category'], unique=False)

    op.create_table('extracted_fields',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('value', sa.String(length=500), nullable=False),
    sa.Column('numeric_value', sa.Float(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('corrected_value', sa.String(length=500), nullable=True),
    sa.Column('corrected_by', sa.Integer(), nullable=True),
    sa.Column('corrected_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['corrected_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('extracted_fields', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_extracted_fields_document_id'), ['document_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('extracted_fields', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_extracted_fields_document_id'))

    op.drop_table('extracted_fields')
    with op.batch_alter_table('verification_checks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_verification_checks_category'))
        batch_op.drop_index(batch_op.f('ix_verification_checks_application_id'))

    op.drop_table('verification_checks')
    with op.batch_alter_table('provider_calls', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_provider_calls_provider'))
        batch_op.drop_index(batch_op.f('ix_provider_calls_application_id'))

    op.drop_table('provider_calls')
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_status'))
        batch_op.drop_index(batch_op.f('ix_documents_sha256'))
        batch_op.drop_index(batch_op.f('ix_documents_doc_type'))
        batch_op.drop_index(batch_op.f('ix_documents_application_id'))

    op.drop_table('documents')
    with op.batch_alter_table('document_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_requests_status'))
        batch_op.drop_index(batch_op.f('ix_document_requests_application_id'))

    op.drop_table('document_requests')
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notifications_user_id'))
        batch_op.drop_index(batch_op.f('ix_notifications_created_at'))
        batch_op.drop_index(batch_op.f('ix_notifications_application_id'))

    op.drop_table('notifications')
    with op.batch_alter_table('decisions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_decisions_outcome'))
        batch_op.drop_index(batch_op.f('ix_decisions_application_id'))

    op.drop_table('decisions')
    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assessments_application_id'))

    op.drop_table('assessments')
    with op.batch_alter_table('applicants', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_applicants_pan'))
        batch_op.drop_index(batch_op.f('ix_applicants_application_id'))

    op.drop_table('applicants')
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_applications_status'))
        batch_op.drop_index(batch_op.f('ix_applications_reference'))
        batch_op.drop_index(batch_op.f('ix_applications_product'))
        batch_op.drop_index(batch_op.f('ix_applications_owner_id'))

    op.drop_table('applications')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_role'))
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    op.drop_table('settings')
    with op.batch_alter_table('policies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_policies_status'))
        batch_op.drop_index(batch_op.f('ix_policies_key'))

    op.drop_table('policies')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_created_at'))
        batch_op.drop_index(batch_op.f('ix_audit_events_application_id'))
        batch_op.drop_index(batch_op.f('ix_audit_events_action'))

    op.drop_table('audit_events')

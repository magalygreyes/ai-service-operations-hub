-- =====================================================================
-- Breezio Service Hub: reference data
-- Slice 1, Phase 3
-- Run after 01_schema.sql. Source: docs/requirements.md §3 and §4.
-- SLA hours = business days x 9 (business day is 8:00 to 17:00).
-- =====================================================================

insert into teams (team_id, team_name, lead_name, coordinator) values
    ('IT',  'IT',         'Priya Raman',  'Jess Park'),
    ('HR',  'HR',         'Aisha Bello',  'Luis Moreno'),
    ('FAC', 'Facilities', 'Tomas Garza',  'Nora Fitzgerald'),
    ('FIN', 'Finance',    'David Mensah', 'Sam Whitaker');

insert into categories
    (category_id, team_id, category_name, required_fields, approval_rule, is_sensitive, sla_business_hours)
values
    ('CAT-IT-01',  'IT',  'Access request',                 '{system,access_level,business_reason}',            'manager',                             false, 18),
    ('CAT-IT-02',  'IT',  'Hardware request',               '{item,business_reason,cost_center}',               'manager',                             false, 45),
    ('CAT-IT-03',  'IT',  'Software request',               '{software_name,license_count,cost_center}',        'manager_plus_finance_over_threshold', false, 27),
    ('CAT-IT-04',  'IT',  'Password or account lockout',    '{system}',                                         'none',                                false, 4.5),
    ('CAT-IT-05',  'IT',  'Something is broken (incident)', '{system_or_device,who_is_affected}',               'none',                                false, 9),
    ('CAT-IT-06',  'IT',  'How-to question',                '{system}',                                         'none',                                false, 18),
    ('CAT-HR-01',  'HR',  'Benefits question',              '{topic}',                                          'none',                                true,  27),
    ('CAT-HR-02',  'HR',  'Payroll question',               '{pay_period}',                                     'none',                                true,  18),
    ('CAT-HR-03',  'HR',  'Leave request',                  '{leave_type,start_date,end_date}',                 'manager',                             true,  18),
    ('CAT-HR-04',  'HR',  'Onboarding or offboarding',      '{employee_name,role,effective_date,manager}',      'none',                                true,  45),
    ('CAT-HR-05',  'HR',  'Employment letter',              '{letter_type,recipient}',                          'none',                                true,  27),
    ('CAT-HR-06',  'HR',  'Policy question',                '{topic}',                                          'none',                                false, 27),
    ('CAT-FAC-01', 'FAC', 'Maintenance or repair',          '{building,floor,room,description}',                'none',                                false, 18),
    ('CAT-FAC-02', 'FAC', 'Workspace or move',              '{current_location,requested_location,move_date}',  'manager',                             false, 90),
    ('CAT-FAC-03', 'FAC', 'Badge or building access',       '{building,access_area,start_date}',                'manager',                             false, 18),
    ('CAT-FIN-01', 'FIN', 'Expense reimbursement',          '{amount,expense_date,receipt,cost_center}',        'manager',                             false, 45),
    ('CAT-FIN-02', 'FIN', 'Purchase request',               '{item_or_service,vendor,amount,cost_center}',      'manager_plus_finance_over_threshold', false, 45),
    ('CAT-FIN-03', 'FIN', 'Vendor or invoice question',     '{vendor_name,invoice_number}',                     'none',                                false, 27),
    ('CAT-GEN-00', null,  'Unclassified',                   '{}',                                               'none',                                false, null);

insert into routing_config (config_key, config_value, description, source) values
    ('auto_route_min_confidence',  0.90, 'Confidence at or above this auto-routes',                     'BR-01, D3'),
    ('flag_min_confidence',        0.70, 'Confidence at or above this routes and flags for review',     'BR-02, D3'),
    ('finance_approval_threshold', 2500, 'Amount above this needs Finance approval after the manager',  'BR-05, D9'),
    ('high_priority_max_sla_hours',   9, 'High priority SLA cap: 1 business day',                       'BR-07'),
    ('stale_after_business_days',     3, 'Open with no status change for this long counts as stale',    'K8'),
    ('auto_close_business_days',      5, 'Resolved requests close after this many business days',       'BR-09'),
    ('inbox_overlap_days',           30, 'Shared inbox auto-reply overlap period',                      'D8');

-- =====================================================================
-- Breezio Service Hub: database schema
-- Slice 1, Phase 3
-- Run once in the Supabase SQL Editor. Safe to re-run: it drops and
-- recreates every object it owns.
-- Design notes: docs/data-model.md
-- =====================================================================

drop table if exists request_events cascade;
drop table if exists approvals cascade;
drop table if exists routing_decisions cascade;
drop table if exists ai_predictions cascade;
drop table if exists requests cascade;
drop table if exists employees cascade;
drop table if exists categories cascade;
drop table if exists teams cascade;
drop table if exists routing_config cascade;
drop function if exists block_event_changes() cascade;

-- ---------------------------------------------------------------------
-- Reference data (NFR-10: rules and taxonomy live in tables, not code)
-- ---------------------------------------------------------------------

create table teams (
    team_id        text primary key,               -- IT, HR, FAC, FIN
    team_name      text not null,
    lead_name      text not null,
    coordinator    text not null
);

create table categories (
    category_id         text primary key,          -- CAT-IT-01
    team_id             text references teams(team_id),  -- null only for CAT-GEN-00
    category_name       text not null,
    required_fields     text[] not null default '{}',
    approval_rule       text not null
        check (approval_rule in ('none', 'manager', 'manager_plus_finance_over_threshold')),
    is_sensitive        boolean not null default false,
    sla_business_hours  numeric(5,1),              -- null only for CAT-GEN-00
    taxonomy_version    integer not null default 1
);

create table routing_config (
    config_key    text primary key,
    config_value  numeric not null,
    description   text not null,
    source        text not null                     -- decision or rule ID
);

create table employees (
    employee_id   text primary key,                -- EMP-0001
    full_name     text not null,
    department    text not null,
    job_title     text not null,
    manager_id    text references employees(employee_id),
    is_manager    boolean not null default false
);

-- ---------------------------------------------------------------------
-- Core tables
-- ---------------------------------------------------------------------

create table requests (
    request_id           text primary key
        check (request_id ~ '^BRZ-[0-9]{4}-[0-9]{5}$'),          -- FR-01
    era                  text not null
        check (era in ('current_state', 'future_state')),       -- FR-58
    requester_id         text not null references employees(employee_id),
    channel              text not null
        check (channel in ('form', 'email', 'chat', 'walk_up')), -- FR-02
    submitted_on_behalf  boolean not null default false,        -- FR-04
    submitted_by_id      text references employees(employee_id),
    submitted_at         timestamptz not null,
    description          text not null,
    has_attachment       boolean not null default false,
    amount               numeric(10,2),                         -- purchases only
    priority             text not null default 'normal'
        check (priority in ('high', 'normal', 'low')),
    true_category_id     text not null references categories(category_id),
    current_team_id      text references teams(team_id),
    current_category_id  text references categories(category_id),
    status               text not null default 'new'
        check (status in ('new', 'triaged', 'awaiting_information',
                          'awaiting_approval', 'in_progress',
                          'resolved', 'closed', 'rejected')),   -- FR-40
    sla_due_at           timestamptz,                           -- FR-23
    resolved_at          timestamptz,
    closed_at            timestamptz,
    taxonomy_version     integer not null default 1,            -- FR-60
    check (submitted_on_behalf = false or submitted_by_id is not null),
    check (resolved_at is null or resolved_at >= submitted_at)
);

create table ai_predictions (
    prediction_id          bigint generated always as identity primary key,
    request_id             text not null references requests(request_id),
    predicted_team_id      text references teams(team_id),
    predicted_category_id  text references categories(category_id),
    predicted_priority     text check (predicted_priority in ('high', 'normal', 'low')),
    confidence             numeric(4,3) check (confidence between 0 and 1),  -- FR-10
    reason                 text,                                             -- FR-11
    missing_fields         text[] not null default '{}',                     -- FR-12
    model_name             text not null,                                    -- FR-13
    prompt_version         text not null,
    is_valid               boolean not null default true,                    -- FR-14
    created_at             timestamptz not null default now()
);

create table routing_decisions (
    decision_id         bigint generated always as identity primary key,
    request_id          text not null references requests(request_id),
    prediction_id       bigint references ai_predictions(prediction_id),
    band                text not null
        check (band in ('auto_route', 'route_and_flag', 'human_triage')),
    rule_applied        text not null
        check (rule_applied in ('BR-01', 'BR-02', 'BR-03', 'BR-04', 'MANUAL')),
    routed_team_id      text references teams(team_id),
    flagged_for_review  boolean not null default false,
    decided_at          timestamptz not null
);

create table approvals (
    approval_id    bigint generated always as identity primary key,
    request_id     text not null references requests(request_id),
    step           smallint not null check (step in (1, 2)),   -- 1 manager, 2 finance
    approver_id    text not null references employees(employee_id),
    approver_role  text not null check (approver_role in ('manager', 'finance')),
    requested_at   timestamptz not null,
    decided_at     timestamptz,
    decision       text not null default 'pending'
        check (decision in ('pending', 'approved', 'rejected')),
    comment        text,
    unique (request_id, step),
    check (decided_at is null or decided_at >= requested_at)
);

-- Append-only event log (NFR-04). Every KPI is computed from here.
create table request_events (
    event_id     bigint generated always as identity primary key,
    request_id   text not null references requests(request_id),
    event_type   text not null
        check (event_type in ('created', 'classified', 'routed', 'rerouted',
                              'status_changed', 'info_requested', 'info_received',
                              'approval_requested', 'approval_decided',
                              'status_inquiry')),
    from_value   text,
    to_value     text,
    actor_id     text references employees(employee_id),
    occurred_at  timestamptz not null
);

create function block_event_changes() returns trigger
language plpgsql as $$
begin
    raise exception 'request_events is append-only (NFR-04)';
end;
$$;

create trigger request_events_append_only
    before update or delete on request_events
    for each row execute function block_event_changes();

-- ---------------------------------------------------------------------
-- Indexes for dashboard filters (NFR-06)
-- ---------------------------------------------------------------------

create index on requests (submitted_at);
create index on requests (current_team_id, status);
create index on requests (era);
create index on request_events (request_id, occurred_at);
create index on request_events (event_type);
create index on approvals (approver_id);

-- ---------------------------------------------------------------------
-- Row level security: on for every table, no public policies.
-- Nothing is readable through Supabase's public API key. The dashboard
-- will connect server-side with its own read-only credentials (Phase 5).
-- ---------------------------------------------------------------------

alter table teams              enable row level security;
alter table categories         enable row level security;
alter table routing_config     enable row level security;
alter table employees          enable row level security;
alter table requests           enable row level security;
alter table ai_predictions     enable row level security;
alter table routing_decisions  enable row level security;
alter table approvals          enable row level security;
alter table request_events     enable row level security;

-- Market Brief multi-user data model.
-- Run once in Supabase Dashboard > SQL Editor as the project owner.
-- Every RPC uses SECURITY INVOKER and the authenticated user's JWT; RLS remains active.

create table if not exists public.user_settings (
    user_id uuid primary key references auth.users (id) on delete cascade,
    watchlist text[] not null default array['AAPL', 'MSFT', 'NVDA', 'LLOY.L', 'SHEL.L']::text[],
    updated_at timestamptz not null default now()
);

create table if not exists public.portfolio_transactions (
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    id text not null,
    trade_date date,
    ticker text not null,
    action text not null check (action in ('Opening', 'Buy', 'Sell')),
    shares numeric(24, 8) not null check (shares > 0),
    price numeric(24, 8) not null check (price >= 0),
    fees numeric(24, 8) not null default 0 check (fees >= 0),
    notes text not null default '',
    created_at timestamptz not null default now(),
    primary key (user_id, id),
    check (action = 'Opening' or price > 0),
    check (action = 'Opening' or trade_date is not null)
);

create index if not exists portfolio_transactions_user_date_idx
    on public.portfolio_transactions (user_id, trade_date, ticker);

create table if not exists public.user_forecasts (
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    id text not null,
    ticker text not null,
    created_at timestamptz not null,
    origin_date date not null,
    target_date date not null,
    horizon integer not null check (horizon > 0),
    lookback integer not null check (lookback > 0),
    method text not null check (method in ('Historical bootstrap', 'EWMA volatility')),
    confidence numeric(5, 4) not null check (confidence > 0 and confidence < 1),
    spot numeric(24, 8) not null check (spot > 0),
    median numeric(24, 8) not null check (median > 0),
    lower numeric(24, 8) not null check (lower > 0),
    upper numeric(24, 8) not null check (upper > 0),
    actual numeric(24, 8),
    actual_date date,
    primary key (user_id, id),
    unique (user_id, ticker, origin_date, horizon, method, lookback, confidence)
);

create index if not exists user_forecasts_user_ticker_target_idx
    on public.user_forecasts (user_id, ticker, target_date);

alter table public.user_settings enable row level security;
alter table public.portfolio_transactions enable row level security;
alter table public.user_forecasts enable row level security;

drop policy if exists "Users manage their own settings" on public.user_settings;
create policy "Users manage their own settings"
    on public.user_settings for all to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "Users manage their own transactions" on public.portfolio_transactions;
create policy "Users manage their own transactions"
    on public.portfolio_transactions for all to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "Users manage their own forecasts" on public.user_forecasts;
create policy "Users manage their own forecasts"
    on public.user_forecasts for all to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

grant select, insert, update, delete on public.user_settings to authenticated;
grant select, insert, update, delete on public.portfolio_transactions to authenticated;
grant select, insert, update, delete on public.user_forecasts to authenticated;

create or replace function public.replace_my_watchlist(p_symbols text[])
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    actor_id uuid := auth.uid();
begin
    if actor_id is null then
        raise exception 'Authentication required';
    end if;

    insert into public.user_settings (user_id, watchlist, updated_at)
    values (actor_id, coalesce(p_symbols, array[]::text[]), now())
    on conflict (user_id) do update
        set watchlist = excluded.watchlist,
            updated_at = now();
end;
$$;

create or replace function public.replace_my_portfolio_transactions(p_rows jsonb)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    actor_id uuid := auth.uid();
begin
    if actor_id is null then
        raise exception 'Authentication required';
    end if;

    delete from public.portfolio_transactions where user_id = actor_id;

    insert into public.portfolio_transactions
        (user_id, id, trade_date, ticker, action, shares, price, fees, notes)
    select
        actor_id,
        row_data.id,
        row_data.trade_date,
        upper(trim(row_data.ticker)),
        row_data.action,
        row_data.shares,
        row_data.price,
        coalesce(row_data.fees, 0),
        coalesce(row_data.notes, '')
    from jsonb_to_recordset(coalesce(p_rows, '[]'::jsonb)) as row_data(
        id text,
        trade_date date,
        ticker text,
        action text,
        shares numeric,
        price numeric,
        fees numeric,
        notes text
    );
end;
$$;

create or replace function public.insert_my_forecast(p_row jsonb)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $$
declare
    actor_id uuid := auth.uid();
    inserted boolean := false;
begin
    if actor_id is null then
        raise exception 'Authentication required';
    end if;

    insert into public.user_forecasts
        (user_id, id, ticker, created_at, origin_date, target_date, horizon, lookback,
         method, confidence, spot, median, lower, upper, actual, actual_date)
    select
        actor_id,
        row_data.id,
        upper(trim(row_data.ticker)),
        row_data.created_at,
        row_data.origin_date,
        row_data.target_date,
        row_data.horizon,
        row_data.lookback,
        row_data.method,
        row_data.confidence,
        row_data.spot,
        row_data.median,
        row_data.lower,
        row_data.upper,
        row_data.actual,
        row_data.actual_date
    from jsonb_to_record(coalesce(p_row, '{}'::jsonb)) as row_data(
        id text,
        ticker text,
        created_at timestamptz,
        origin_date date,
        target_date date,
        horizon integer,
        lookback integer,
        method text,
        confidence numeric,
        spot numeric,
        median numeric,
        lower numeric,
        upper numeric,
        actual numeric,
        actual_date date
    )
    on conflict (user_id, ticker, origin_date, horizon, method, lookback, confidence) do nothing
    returning true into inserted;

    return coalesce(inserted, false);
end;
$$;

revoke all on function public.replace_my_watchlist(text[]) from public, anon;
revoke all on function public.replace_my_portfolio_transactions(jsonb) from public, anon;
revoke all on function public.insert_my_forecast(jsonb) from public, anon;
grant execute on function public.replace_my_watchlist(text[]) to authenticated;
grant execute on function public.replace_my_portfolio_transactions(jsonb) to authenticated;
grant execute on function public.insert_my_forecast(jsonb) to authenticated;

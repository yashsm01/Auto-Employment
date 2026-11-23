-- Links profiles to Supabase Auth users. Does nothing on plain Postgres.

do $$
begin
    if to_regclass('auth.users') is not null then
        alter table profiles
            add constraint profiles_user_id_fkey
            foreign key (user_id) references auth.users (id) on delete cascade;
    end if;
end
$$;

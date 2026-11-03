# Invite-only accounts and private user data

Market Brief uses Supabase Auth for invite-only email-code sign-in and Supabase Postgres for each user's portfolio transactions, watchlist, and forecast history. The app does not include public registration or an in-app user admin screen. The owner invites accounts in the Supabase dashboard.

## 1. Create the Supabase project

Create a project in the Supabase dashboard and keep its database password in your password manager. In **SQL Editor**, run the complete [`supabase_schema.sql`](supabase_schema.sql) file. It creates the user tables, row-level security policies, and user-scoped database functions.

The policies use the authenticated user's ID. The app sends each user's access token with data requests, and Postgres only returns or changes that user's rows. Do not put a Supabase secret/service-role key in the app; those keys bypass row-level security. The app only needs the project URL and publishable (or legacy anon) key.

## 2. Configure email sign-in

In Supabase Auth settings:

1. Enable email authentication.
2. Configure a custom SMTP provider before inviting people outside your Supabase organization. Supabase's default email service is for trying the product and restricts recipients to team addresses; see [Supabase SMTP guidance](https://supabase.com/docs/guides/auth/auth-smtp).
3. Open **Email Templates → Magic Link** and include the one-time token in the message body. For example:

   ```html
   <h2>Market Brief sign-in code</h2>
   <p>Enter this one-time code in the app:</p>
   <p><strong>{{ .Token }}</strong></p>
   <p>If you did not request a code, you can ignore this email.</p>
   ```

   The app uses the OTP endpoint with account creation disabled, so an email address must already belong to an invited account. Supabase documents the `{{ .Token }}` template variable and OTP verification in its [email sign-in guide](https://supabase.com/docs/guides/auth/auth-email-passwordless).
4. Set the Auth **Site URL** to `https://ivestment-app-1.streamlit.app` and add that URL to the allowed redirect URLs. This is used by the invitation email's accept link.

## 3. Add the project URL and key to Streamlit

Open the deployed app's settings on Streamlit Community Cloud and paste this into **Secrets**, using the values from your Supabase project's API settings:

```toml
[supabase]
url = "https://YOUR_PROJECT_REF.supabase.co"
anon_key = "YOUR_PUBLISHABLE_OR_ANON_KEY"
```

Use the publishable key (or legacy anon key), never a secret/service-role key. Row-level security must be enabled; it is enabled by `supabase_schema.sql`.

For local development, create `.streamlit/secrets.toml` with the same contents. That file is ignored by Git. Never commit it.

## 4. Deploy the authentication code

Add the Streamlit secret and run the schema **before** pushing the authentication update. The updated app fails closed and displays an account-setup message when the Supabase secrets are missing; setting them first avoids taking the dashboard offline during the change.

After the code is deployed, sign in with the owner's invited email and verify that the dashboard opens. The local `data/portfolio.json` and `data/transactions.json` are not uploaded or imported automatically. Keep those files as a backup; the new database begins with an empty ledger.

## 5. Invite people

In Supabase, open **Authentication → Users → Add user → Send invitation** and enter the person's email. Once they accept the invite, they can open the Streamlit URL, request a sign-in code, and verify it. Repeat this for each person. The app will not create an account for an uninvited email.

Each signed-in user has a separate transaction ledger, watchlist, and forecast history. Market prices, news, and daily market reports are shared dashboard content. Sign out before another person uses the same browser profile.

## What remains local

The generated daily Markdown reports are still files in `reports/`; they are not stored per user in Supabase. Streamlit Community Cloud does not guarantee local file persistence, so treat the cloud report archive as temporary. A later update can put shared report archives in object storage or a database if they need to persist.

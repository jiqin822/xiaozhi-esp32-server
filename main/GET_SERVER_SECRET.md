# How to Get the Server Secret (服务器密钥)

The server secret is stored in the database and is used to authenticate requests from the Python server to the Java API.

## Method 1: Query Database Directly

Connect to your MySQL database and run:

```sql
SELECT param_value FROM sys_params WHERE param_code = 'server.secret';
```

## Method 2: Check Java API Startup Logs

When the Java API server starts, it automatically generates a server secret if one doesn't exist. Check the startup logs for any messages about server secret initialization.

## Method 3: Use Web UI (System Parameters)

1. Log in to the web management interface
2. Go to **System Management** → **Parameter Management** (系统管理 → 参数管理)
3. Search for parameter code: `server.secret`
4. View the parameter value

## Method 4: Query via API (if authenticated)

If you have admin access, you can query the system parameters API:

```bash
GET /pingping/admin/sys/params?paramCode=server.secret
Authorization: Bearer {your_admin_token}
```

## Method 5: Check Python Server Config

The server secret should be configured in your Python server's config file:

**File:** `pingping-server/data/.config.yaml`

```yaml
manager-api:
  url: http://localhost:8002/pingping
  secret: YOUR_SERVER_SECRET_HERE
```

If this is not set, you need to:
1. Get the secret from the database (Method 1)
2. Add it to your config file

## Important Notes

- The server secret is automatically generated on first startup if it doesn't exist (UUID format)
- The secret must match exactly between:
  - Database: `sys_params` table, `param_code = 'server.secret'`
  - Python config: `data/.config.yaml`, `manager-api.secret`
- If you change the secret in the database, you must update the Python config file as well
- The secret is used in the `Authorization: Bearer {secret}` header for all `/config/*` API calls


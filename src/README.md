# Slalom Capabilities Management API

<p align="center">
  <img src="./.images/byte-teacher.png" alt="Byte Teacher" width="200" />
</p>

A FastAPI application that enables Slalom consultants to register their capabilities and manage consulting expertise across the organization.

## Features

- View all available consulting capabilities
- Register consultant expertise and availability
- Track skill levels and certifications
- Manage capability capacity and team assignments

## Getting Started

1. From the repository root, install the dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Provision at least one practice lead and one consultant account. Accounts are stored in `src/auth_users.json` with PBKDF2-SHA256 password hashes; the file is ignored by Git.

   ```
   python src/manage_users.py lead@slalom.com practice_lead --practice-areas Technology,Strategy,Operations
   python src/manage_users.py consultant@slalom.com consultant
   ```

   The command prompts for each password and confirmation. Practice leads can be assigned one or more practice areas, or `*` for all areas.

3. Set a stable session secret and run the application:

   ```sh
   export SESSION_SECRET="$(openssl rand -hex 32)"
   uvicorn app:app --app-dir src --reload
   ```

4. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc
   - Capabilities Dashboard: http://localhost:8000/

For HTTPS deployments, set `COOKIE_SECURE=true`. Successful logins and capability changes are recorded in the ignored `src/auth_audit.jsonl` file. Consultants can request capability registrations; an authorized practice lead must approve them. Leads can update capacity, skill levels, and certifications, and view a summary report for their assigned practice areas.

This exercise uses a local JSON account store and in-memory capability data. It does not include email verification, login rate limiting, durable capability storage, or enterprise SSO. Use a managed identity provider and persistent database before exposing it as a production service.

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/capabilities`                                                   | Get all capabilities with details and current consultant assignments |
| POST   | `/capabilities/{capability_name}/register?email=consultant@slalom.com` | Register consultant for a capability                     |
| DELETE | `/capabilities/{capability_name}/unregister?email=consultant@slalom.com` | Unregister consultant from a capability              |

## Data Model

The application uses a consulting-focused data model:

1. **Capabilities** - Uses capability name as identifier:
   - Description of the consulting capability
   - Skill levels (Emerging, Proficient, Advanced, Expert)
   - Practice area (Strategy, Technology, Operations)
   - Industry verticals served
   - Required certifications
   - List of consultant emails registered
   - Available capacity (hours per week)
   - Geographic location preferences

2. **Consultants** - Uses email as identifier:
   - Name
   - Practice area
   - Skill level
   - Certifications
   - Availability

All data is currently stored in memory for this learning exercise. In a production environment, this would be backed by a robust database system.

## Future Enhancements

This exercise will guide you through implementing:
- Capability maturity assessments
- Intelligent team matching algorithms  
- Analytics dashboards for practice leads
- Integration with project management systems
- Advanced search and filtering capabilities

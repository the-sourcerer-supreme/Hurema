# Odoo Hackathon Authentication Backend

A production-ready FastAPI backend for user authentication and registration system designed for the Odoo Hackathon platform.

## Features

✅ **User Registration** - Create new user accounts with email validation
✅ **User Login** - Authenticate users with JWT tokens
✅ **JWT Authentication** - Secure token-based authentication
✅ **Password Hashing** - bcrypt secure password storage
✅ **Role-based Support** - User roles for future expansion
✅ **Protected Routes** - JWT-secured endpoints
✅ **Forgot Password** - Password reset functionality
✅ **PostgreSQL Database** - Async database operations with SQLAlchemy
✅ **Input Validation** - Pydantic schema validation
✅ **Error Handling** - Comprehensive error responses
✅ **CORS Support** - Cross-origin resource sharing configured
✅ **Modular Architecture** - Clean separation of concerns

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with asyncpg
- **ORM**: SQLAlchemy (async)
- **Authentication**: JWT (python-jose) + bcrypt
- **Validation**: Pydantic
- **Server**: Uvicorn
- **Environment**: python-dotenv

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── core/
│   │   ├── config.py          # Configuration and settings
│   │   ├── security.py        # JWT and password utilities
│   │   └── database.py        # Database setup and connection
│   ├── models/
│   │   └── user.py            # SQLAlchemy User model
│   ├── schemas/
│   │   ├── user.py            # Pydantic user schemas
│   │   └── token.py           # JWT token schemas
│   ├── crud/
│   │   └── user.py            # Database operations
│   ├── api/
│   │   └── routes/
│   │       └── auth.py        # Authentication endpoints
│   ├── services/
│   │   └── auth_service.py    # Business logic
│   └── utils/
│       └── dependencies.py    # FastAPI dependencies
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Prerequisites

- Python 3.9+
- PostgreSQL 12+
- pip or conda

## Installation & Setup

### 1. Clone/Navigate to Project
```bash
cd backend
```

### 2. Create Virtual Environment
```bash
# Using venv
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create/Edit `.env` file with your database credentials:

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:Neeraj%401907@localhost:5432/odoo_hackathon

# JWT Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application Settings
DEBUG=True
APP_NAME=Odoo Hackathon Auth API
APP_VERSION=1.0.0

# CORS Settings
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]

# Email Configuration (optional, for future password reset functionality)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=your-email@gmail.com
```

### 5. Create PostgreSQL Database

```bash
# Using psql
psql -U postgres

# Inside psql:
CREATE DATABASE odoo_hackathon;
\q
```

### 6. Run the Application

```bash
# Start the development server
uvicorn app.main:app --reload

# The server will be available at:
# http://localhost:8000

# API Documentation:
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

## API Endpoints

### 1. Register New User
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "full_name": "John Doe",
  "password": "securepassword123",
  "role": "user"
}

Response (201):
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "user",
  "is_active": true,
  "created_at": "2024-01-01T12:00:00"
}
```

### 2. User Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response (200):
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 3. Get User Profile (Protected)
```http
GET /auth/me
Authorization: Bearer {access_token}

Response (200):
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "user",
  "is_active": true,
  "created_at": "2024-01-01T12:00:00"
}
```

### 4. Request Password Reset
```http
POST /auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}

Response (200):
{
  "message": "If the email exists in our system, you will receive a password reset link",
  "status": "success"
}
```

### 5. User Logout
```http
POST /auth/logout

Response (200):
{
  "message": "Logout successful. Please remove the token from client storage",
  "status": "success"
}
```

### 6. Health Check
```http
GET /health

Response (200):
{
  "status": "healthy",
  "service": "Odoo Hackathon Auth API",
  "version": "1.0.0"
}
```

## Database Schema

### Users Table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

## Authentication Flow

1. **Register**: User provides email, full name, password → Backend hashes password, stores in DB
2. **Login**: User provides email, password → Backend verifies credentials → JWT token issued
3. **Protected Routes**: Client sends JWT in Authorization header → Backend validates token → Returns user data
4. **Token Validation**: Each request includes Bearer token → Decoded and verified → User identity confirmed

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- `200 OK` - Successful request
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid input/request
- `401 Unauthorized` - Invalid credentials or expired token
- `403 Forbidden` - Access denied (inactive user)
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

## Security Features

✅ **Password Hashing**: bcrypt with 12 rounds
✅ **JWT Tokens**: Signed with secret key
✅ **Email Validation**: Pydantic EmailStr validator
✅ **CORS Protection**: Configured allowed origins
✅ **Password Requirements**: Minimum 8 characters
✅ **User Status Check**: Only active users can login
✅ **Token Expiration**: 30-minute default expiration

## Deployment Notes

### Production Checklist

- [ ] Change `DEBUG=False` in production
- [ ] Use strong `SECRET_KEY` (generate with: `openssl rand -hex 32`)
- [ ] Update `CORS_ORIGINS` with your frontend URL
- [ ] Configure email settings for password reset
- [ ] Use environment-specific `.env` files
- [ ] Enable HTTPS for all endpoints
- [ ] Set up database backups
- [ ] Configure logging
- [ ] Use a production ASGI server (gunicorn + uvicorn)
- [ ] Set up monitoring and alerting

### Running with Gunicorn (Production)

```bash
pip install gunicorn

gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

## Future Enhancements

- Email verification for registration
- OAuth2 integration (Google, GitHub)
- Two-factor authentication
- User profile update endpoint
- Refresh token mechanism
- Rate limiting
- API key authentication
- Admin dashboard
- User activity logging
- Email notifications

## Testing

```bash
# Coming soon: Test suite with pytest
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Follow the existing code structure
4. Test thoroughly
5. Submit a pull request

## License

MIT License - Feel free to use this project

## Support

For issues or questions:
- Check the API documentation at `/docs`
- Review error messages for guidance
- Check database connections and credentials

## Team Collaboration

This backend is designed for team development:

- **Modular Structure**: Each feature in its own module
- **Clear Separation**: Business logic, database, API separated
- **Easy to Extend**: Add new endpoints and features without touching core
- **Documented Code**: Comments and docstrings throughout
- **Async-Ready**: Built for high concurrency

---

**Built with ❤️ for the Odoo Hackathon**

Happy coding! 🚀

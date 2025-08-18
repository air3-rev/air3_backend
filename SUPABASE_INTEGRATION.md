# Supabase Integration Guide

This guide explains how to integrate your frontend application with this FastAPI backend that uses Supabase authentication.

## Overview

- **Frontend**: Handles user authentication through Supabase
- **Backend**: Validates Supabase JWT tokens and manages application data
- **Flow**: Frontend authenticates → Backend validates tokens → API access granted

## Setup

### 1. Environment Configuration

Copy `.env.example` to `.env` and configure:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
```

### 2. Frontend Integration

#### Authentication Flow

```javascript
// 1. Initialize Supabase client in your frontend
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://your-project.supabase.co',
  'your-supabase-anon-key'
)

// 2. Authenticate user (sign up/sign in)
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'password'
})

// 3. Get session and token
const { data: { session } } = await supabase.auth.getSession()
const token = session?.access_token
```

#### API Calls with Authentication

```javascript
// Helper function for authenticated API calls
async function apiCall(endpoint, options = {}) {
  const { data: { session } } = await supabase.auth.getSession()
  
  const headers = {
    'Content-Type': 'application/json',
    ...(session && { 'Authorization': `Bearer ${session.access_token}` }),
    ...options.headers
  }

  const response = await fetch(`http://localhost:8000${endpoint}`, {
    ...options,
    headers
  })

  return response.json()
}

// Examples:
// Get current user profile
const profile = await apiCall('/api/v1/users/me')

// Create an item
const newItem = await apiCall('/api/v1/items/', {
  method: 'POST',
  body: JSON.stringify({
    title: 'My Item',
    description: 'Item description'
  })
})
```

#### User Synchronization

After successful Supabase authentication, sync the user with your backend:

```javascript
async function syncUserWithBackend(user) {
  try {
    await fetch('http://localhost:8000/api/v1/users/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        supabase_id: user.id,
        email: user.email,
        full_name: user.user_metadata?.full_name || null,
        avatar_url: user.user_metadata?.avatar_url || null
      })
    })
  } catch (error) {
    console.error('Failed to sync user:', error)
  }
}

// Call after successful authentication
supabase.auth.onAuthStateChange(async (event, session) => {
  if (event === 'SIGNED_IN' && session?.user) {
    await syncUserWithBackend(session.user)
  }
})
```

## API Endpoints

### Public Endpoints (No Authentication Required)

```javascript
// Get all users
GET /api/v1/users/

// Get user by ID
GET /api/v1/users/{user_id}

// Get all public items
GET /api/v1/items/all

// Search items
GET /api/v1/items/search?q=query

// Health check
GET /health
```

### Protected Endpoints (Require Authentication)

```javascript
// User endpoints
GET /api/v1/users/me          // Get current user
PUT /api/v1/users/me          // Update current user
POST /api/v1/users/sync       // Sync user from Supabase

// Item endpoints
POST /api/v1/items/           // Create item
GET /api/v1/items/my-items    // Get user's items
PUT /api/v1/items/{id}        // Update item (owner only)
DELETE /api/v1/items/{id}     // Delete item (owner only)
```

## React Example

```jsx
import { useEffect, useState } from 'react'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.REACT_APP_SUPABASE_URL,
  process.env.REACT_APP_SUPABASE_ANON_KEY
)

function App() {
  const [session, setSession] = useState(null)
  const [items, setItems] = useState([])

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) syncUser(session.user)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        setSession(session)
        if (event === 'SIGNED_IN' && session?.user) {
          await syncUser(session.user)
        }
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const syncUser = async (user) => {
    try {
      await fetch('http://localhost:8000/api/v1/users/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          supabase_id: user.id,
          email: user.email,
          full_name: user.user_metadata?.full_name,
          avatar_url: user.user_metadata?.avatar_url
        })
      })
    } catch (error) {
      console.error('Sync failed:', error)
    }
  }

  const fetchItems = async () => {
    const headers = session ? {
      'Authorization': `Bearer ${session.access_token}`
    } : {}

    const response = await fetch('http://localhost:8000/api/v1/items/', {
      headers
    })
    const data = await response.json()
    setItems(data)
  }

  const signIn = async (email, password) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password
    })
    if (error) console.error('Sign in error:', error)
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    if (error) console.error('Sign out error:', error)
  }

  return (
    <div>
      {session ? (
        <div>
          <p>Welcome, {session.user.email}!</p>
          <button onClick={signOut}>Sign Out</button>
          <button onClick={fetchItems}>Load Items</button>
          <ul>
            {items.map(item => (
              <li key={item.id}>{item.title}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div>
          <button onClick={() => signIn('user@example.com', 'password')}>
            Sign In
          </button>
        </div>
      )}
    </div>
  )
}

export default App
```

## Error Handling

The API returns standard HTTP status codes:

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `500` - Internal Server Error

Example error response:
```json
{
  "message": "Could not validate credentials",
  "status_code": 401
}
```

## Development Tips

1. **CORS Configuration**: Make sure your frontend URL is in `CORS_ORIGINS`
2. **Token Refresh**: Supabase handles token refresh automatically
3. **Error Handling**: Always handle authentication errors gracefully
4. **User Sync**: Call the sync endpoint after successful authentication
5. **Testing**: Use the `/health` endpoint to verify API connectivity

## Production Considerations

1. Use environment variables for all sensitive data
2. Configure proper CORS origins (no wildcards)
3. Set up proper error monitoring
4. Implement rate limiting if needed
5. Use HTTPS in production
6. Monitor Supabase usage and quotas
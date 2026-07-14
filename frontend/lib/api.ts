import { AnalysisResult, ConnectorType, VMInfo } from "@/lib/types";

// Base URL of the backend API. Defaults to localhost for local dev so
// `npm run dev` keeps working without any extra configuration. In production
// (e.g. on Vercel), set NEXT_PUBLIC_API_URL to the deployed backend's URL.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let token: string | null = null;

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem('token', t);
  else localStorage.removeItem('token');
}

export function getToken() {
  if (token) return token;
  return localStorage.getItem('token');
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'sre' | 'viewer';
  organization_id: string;
  organization_name: string;
  is_active?: boolean;
  last_login?: string;
}

// 🟢 Replace the apiRequest function in lib/api.ts
export async function apiRequest(endpoint: string, options: RequestInit = {}) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  
  const authToken = getToken();
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  
  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: headers as HeadersInit,
  });
  
  if (res.status === 401) {
    setToken(null);
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  
  return res.json();
}

export async function login(email: string, password: string) {
  const data = await apiRequest('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data;
}

export async function register(email: string, password: string, full_name: string) {
  return apiRequest('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name }),
  });
}

export async function getCurrentUser(): Promise<User> {
  return apiRequest('/api/auth/me');
}

export async function createUser(userData: { email: string, full_name: string, role: string, password: string }): Promise<User> {
  return apiRequest('/api/users', {
    method: 'POST',
    body: JSON.stringify(userData),
  });
}

export async function deleteUser(userId: string): Promise<void> {
  return apiRequest(`/api/users/${userId}`, { method: 'DELETE' });
}

export async function updateUserRole(userId: string, role: 'admin' | 'sre' | 'viewer'): Promise<User> {
  return apiRequest(`/api/users/${userId}/role`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  });
}

export async function analyzeLogs(logs: string, domain: string = 'kubernetes') {
  return apiRequest('/api/analyze', {
    method: 'POST',
    body: JSON.stringify({ logs, domain }),
  });
}

export async function analyzeIncident(payload: { sources: ConnectorType[], logs?: string, domain?: string, vm_targets?: string[] }) {
  return apiRequest('/api/incidents/analyze', {
    method: 'POST',
    body: JSON.stringify({
      sources: payload.sources,
      logs: payload.logs,
      domain: payload.domain || 'infrastructure',
      vm_targets: payload.vm_targets
    }),
  });
}

export async function executeAction(actionId: string, confirm: boolean = false) {
  return apiRequest(`/api/actions/${encodeURIComponent(actionId)}/execute`, {
    method: 'POST',
    body: JSON.stringify({ confirm })
  });
}

export async function listVMs(): Promise<VMInfo[]> {
  return apiRequest('/api/vms');
}
 
export async function setVMCredentials(vmName: string, username: string, password: string) {
  return apiRequest(`/api/vms/${encodeURIComponent(vmName)}/credentials`, {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}
 
export async function deleteVMCredentials(vmName: string) {
  return apiRequest(`/api/vms/${encodeURIComponent(vmName)}/credentials`, { method: 'DELETE' });
}

export async function getAnalyses() {
  return apiRequest('/api/analyses');
}

export async function getUsers(): Promise<User[]> {
  return apiRequest('/api/org/users');
}

export interface AnalysisHistory {
  id: string;
  domain: string;
  status: string;
  created_at: string;
  result: AnalysisResult | null;
}

export async function getAnalysisHistory(): Promise<AnalysisHistory[]> {
  return apiRequest('/api/analyses');
}

export async function getAnalysisById(id: string): Promise<AnalysisHistory> {
  return apiRequest(`/api/analyses/${id}`);
}

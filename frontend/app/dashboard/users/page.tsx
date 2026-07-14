"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getUsers, getCurrentUser, User, deleteUser, updateUserRole, createUser } from "@/lib/api";
import { UserPlus, Trash2, X, AlertCircle } from "lucide-react";
import AppHeader from "@/components/AppHeader";

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const router = useRouter();

  // Form State
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserFullname, setNewUserFullname] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserRole, setNewUserRole] = useState<"admin" | "sre" | "viewer">("viewer");

  useEffect(() => {
    const init = async () => {
      try {
        // 1. Verify auth first
        const user = await getCurrentUser();
        setCurrentUser(user);
        
        // 2. Role check
        if (user.role !== "admin") {
          router.push("/dashboard");
          return;
        }
        
        // 3. Fetch users only after auth & role verified
        const userList = await getUsers();
        setUsers(userList);
      } catch (err: any) {
        // Only redirect on actual auth failure
        if (err.message.includes("Unauthorized") || err.message.includes("401")) {
          router.push("/login");
        } else {
          console.error("User management load error:", err);
          setError("Failed to load users. Please refresh or check backend.");
        }
      } finally {
        setLoading(false);
      }
    };
    
    init();
  }, [router]);

  const handleDeleteUser = async (userId: string, userEmail: string) => {
    if (!confirm(`Permanently delete ${userEmail}? This cannot be undone.`)) return;
    try {
      await deleteUser(userId);
      setUsers(prev => prev.filter(u => u.id !== userId));
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const handleCreateUser = async () => {
    if (!newUserEmail || !newUserFullname || !newUserPassword) {
      alert("Please fill all fields");
      return;
    }
    try {
      const newUser = await createUser({
        email: newUserEmail,
        full_name: newUserFullname,
        password: newUserPassword,
        role: newUserRole
      });
      setUsers(prev => [...prev, newUser]);
      setShowCreateModal(false);
      setNewUserEmail("");
      setNewUserFullname("");
      setNewUserPassword("");
      setNewUserRole("viewer");
    } catch (err: any) {
      alert(`Create failed: ${err.message}`);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await updateUserRole(userId, newRole as any);
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole as any } : u));
    } catch (err: any) {
      alert(`Role update failed: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!currentUser) return null;

  return (
    <div className="min-h-screen bg-slate-950">
      <AppHeader user={currentUser} />

      <main className="w-full px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">User Management</h1>
            <p className="text-sm text-slate-400">{currentUser.organization_name}</p>
          </div>
          <button 
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <UserPlus className="h-4 w-4" /> Create User
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-700 rounded-lg flex items-center gap-3 text-red-300">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
            <button onClick={() => window.location.reload()} className="ml-auto text-sm underline hover:text-red-200">
              Retry
            </button>
          </div>
        )}

        {/* Users Table */}
        <div className="glass rounded-lg border border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-900/50 border-b border-slate-700">
                <tr>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">User</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">Role</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">Status</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">Last Login</th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-slate-400 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                      No users found. Create your first team member.
                    </td>
                  </tr>
                ) : (
                  users.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-200">{user.full_name}</div>
                        <div className="text-sm text-slate-500">{user.email}</div>
                      </td>
                      <td className="px-6 py-4">
                        <select
                          value={user.role}
                          onChange={(e) => handleRoleChange(user.id, e.target.value)}
                          disabled={user.id === currentUser.id}
                          className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200 disabled:opacity-50 focus:ring-2 focus:ring-blue-500 outline-none"
                        >
                          <option value="viewer">Viewer</option>
                          <option value="sre">SRE</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          user.is_active !== false ? 'bg-emerald-900/30 text-emerald-400' : 'bg-red-900/30 text-red-400'
                        }`}>
                          {user.is_active !== false ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-400">
                        {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {user.id !== currentUser.id && (
                          <button
                            onClick={() => handleDeleteUser(user.id, user.email)}
                            className="text-red-400 hover:text-red-300 p-2 hover:bg-red-900/20 rounded transition-colors"
                            title="Delete user"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Create User Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm p-4">
            <div className="glass bg-slate-900 p-6 rounded-xl w-full max-w-md border border-slate-700 shadow-2xl">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-slate-100">Create New User</h2>
                <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white transition-colors">
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Full Name</label>
                  <input 
                    value={newUserFullname}
                    onChange={(e) => setNewUserFullname(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                    placeholder="John Doe"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Email</label>
                  <input 
                    type="email"
                    value={newUserEmail}
                    onChange={(e) => setNewUserEmail(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                    placeholder="john@company.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
                  <input 
                    type="password"
                    value={newUserPassword}
                    onChange={(e) => setNewUserPassword(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                    placeholder="••••••••"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Role</label>
                  <select 
                    value={newUserRole}
                    onChange={(e) => setNewUserRole(e.target.value as any)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                  >
                    <option value="viewer">Viewer (Read-only)</option>
                    <option value="sre">SRE (Run analysis)</option>
                    <option value="admin">Admin (Full access)</option>
                  </select>
                </div>
                
                <button 
                  onClick={handleCreateUser}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium text-white mt-2 transition-colors shadow-lg shadow-blue-900/20"
                >
                  Create User
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
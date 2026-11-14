import { lazy, Suspense } from "react"
import { Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider, useAuth } from "@/lib/auth-context"
import { ToastProviderWrapper } from "@/components/ui/toast"
import { Layout } from "@/components/layout/Layout"

const Landing = lazy(() => import("@/pages/Landing").then(({ Landing }) => ({ default: Landing })))
const UserDashboard = lazy(() => import("@/pages/user/UserDashboard").then(({ UserDashboard }) => ({ default: UserDashboard })))
const ExploreOpportunities = lazy(() => import("@/pages/user/ExploreOpportunities").then(({ ExploreOpportunities }) => ({ default: ExploreOpportunities })))
const OpportunityDetail = lazy(() => import("@/pages/user/OpportunityDetail").then(({ OpportunityDetail }) => ({ default: OpportunityDetail })))
const SavedOpportunities = lazy(() => import("@/pages/user/SavedOpportunities").then(({ SavedOpportunities }) => ({ default: SavedOpportunities })))
const NotificationsPage = lazy(() => import("@/pages/user/NotificationsPage").then(({ NotificationsPage }) => ({ default: NotificationsPage })))
const UserProfile = lazy(() => import("@/pages/user/UserProfile").then(({ UserProfile }) => ({ default: UserProfile })))
const AdminDashboard = lazy(() => import("@/pages/admin/AdminDashboard").then(({ AdminDashboard }) => ({ default: AdminDashboard })))
const AdminCollectors = lazy(() => import("@/pages/admin/AdminCollectors").then(({ AdminCollectors }) => ({ default: AdminCollectors })))
const AdminDataQuality = lazy(() => import("@/pages/admin/AdminDataQuality").then(({ AdminDataQuality }) => ({ default: AdminDataQuality })))
const AdminScheduler = lazy(() => import("@/pages/admin/AdminScheduler").then(({ AdminScheduler }) => ({ default: AdminScheduler })))
const AdminAnalytics = lazy(() => import("@/pages/admin/AdminAnalytics").then(({ AdminAnalytics }) => ({ default: AdminAnalytics })))
const AdminAuditLogs = lazy(() => import("@/pages/admin/AdminAuditLogs").then(({ AdminAuditLogs }) => ({ default: AdminAuditLogs })))
const AdminUsers = lazy(() => import("@/pages/admin/AdminUsers").then(({ AdminUsers }) => ({ default: AdminUsers })))
const Login = lazy(() => import("@/pages/auth/Login").then(({ Login }) => ({ default: Login })))
const Register = lazy(() => import("@/pages/auth/Register").then(({ Register }) => ({ default: Register })))
const AdminVerifyOtp = lazy(() => import("@/pages/auth/AdminVerifyOtp").then(({ AdminVerifyOtp }) => ({ default: AdminVerifyOtp })))
const ForgotPassword = lazy(() => import("@/pages/auth/ForgotPassword").then(({ ForgotPassword }) => ({ default: ForgotPassword })))

function PageLoading() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="flex flex-col items-center space-y-3">
        <div className="h-8 w-8 rounded-full border-2 border-cyber-blue border-t-transparent animate-spin" />
        <p className="text-xs text-muted-foreground font-mono">Loading page...</p>
      </div>
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center space-y-3">
          <div className="h-8 w-8 rounded-full border-2 border-cyber-blue border-t-transparent animate-spin" />
          <p className="text-xs text-muted-foreground font-mono">Authenticating session...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-cyber-blue border-t-transparent animate-spin" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (!user?.is_admin) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProviderWrapper>
        <Suspense fallback={<PageLoading />}>
          <Routes>
            {/* Public Landing & Marketing */}
            <Route path="/" element={<Landing />} />

            {/* Public Auth Routes (Both root and /app aliases) */}
            <Route path="/login" element={<Login />} />
            <Route path="/app/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/app/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/app/forgot-password" element={<ForgotPassword />} />
            <Route path="/admin/login" element={<Login />} />
            <Route path="/admin/verify-otp" element={<AdminVerifyOtp />} />
            <Route path="/app/admin/verify-otp" element={<AdminVerifyOtp />} />

            {/* Protected Root-Level Application Layout */}
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              {/* User Portal */}
              <Route path="/dashboard" element={<UserDashboard />} />
              <Route path="/opportunities" element={<ExploreOpportunities />} />
              <Route path="/opportunities/:id" element={<OpportunityDetail />} />
              <Route path="/saved" element={<SavedOpportunities />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/profile" element={<UserProfile />} />

              {/* Admin Portal */}
              <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
              <Route path="/admin/dashboard" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
              <Route path="/admin/collectors" element={<AdminRoute><AdminCollectors /></AdminRoute>} />
              <Route path="/admin/data-quality" element={<AdminRoute><AdminDataQuality /></AdminRoute>} />
              <Route path="/admin/scheduler" element={<AdminRoute><AdminScheduler /></AdminRoute>} />
              <Route path="/admin/analytics" element={<AdminRoute><AdminAnalytics /></AdminRoute>} />
              <Route path="/admin/logs" element={<AdminRoute><AdminAuditLogs /></AdminRoute>} />
              <Route path="/admin/users" element={<AdminRoute><AdminUsers /></AdminRoute>} />
            </Route>

            {/* Protected /app/* Alias Application Layout */}
            <Route
              path="/app"
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/app/dashboard" replace />} />
              <Route path="dashboard" element={<UserDashboard />} />
              <Route path="opportunities" element={<ExploreOpportunities />} />
              <Route path="opportunities/:id" element={<OpportunityDetail />} />
              <Route path="saved" element={<SavedOpportunities />} />
              <Route path="notifications" element={<NotificationsPage />} />
              <Route path="profile" element={<UserProfile />} />

              <Route path="admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
              <Route path="admin/dashboard" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
              <Route path="admin/collectors" element={<AdminRoute><AdminCollectors /></AdminRoute>} />
              <Route path="admin/data-quality" element={<AdminRoute><AdminDataQuality /></AdminRoute>} />
              <Route path="admin/scheduler" element={<AdminRoute><AdminScheduler /></AdminRoute>} />
              <Route path="admin/analytics" element={<AdminRoute><AdminAnalytics /></AdminRoute>} />
              <Route path="admin/logs" element={<AdminRoute><AdminAuditLogs /></AdminRoute>} />
              <Route path="admin/users" element={<AdminRoute><AdminUsers /></AdminRoute>} />
            </Route>

            {/* Catch-all route */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ToastProviderWrapper>
    </AuthProvider>
  )
}

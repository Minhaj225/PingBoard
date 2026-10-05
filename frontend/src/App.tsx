import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ToastProvider } from '@/features/toast/ToastProvider'
import { router } from '@/routes'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 401 is handled by the axios interceptor (silent refresh), and no 4xx
      // becomes correct by being retried. Only 5xx and network errors are.
      retry: (failureCount, error) => {
        const status = (error as { response?: { status?: number } }).response?.status
        if (status && status >= 400 && status < 500) return false
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
    mutations: { retry: false },
  },
})

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        {/* Toasts live above the router so any page can raise one.
            AuthProvider is mounted per-route (see routes.tsx) so the public
            status page never runs an auth bootstrap. */}
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

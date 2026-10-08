import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import { AuthProvider } from '@/features/auth/AuthProvider'
import userEvent from '@testing-library/user-event'
import { LoginPage } from '@/pages/LoginPage'

describe('LoginForm', () => {
  it('renders the login form wrapped in AuthProvider', () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    )

    const form = screen.getByRole('form')
    expect(form).toBeInTheDocument()

    const emailInput = screen.getByLabelText('Email')
    expect(emailInput).toBeInTheDocument()

    const passwordInput = screen.getByLabelText('Password')
    expect(passwordInput).toBeInTheDocument()

    const submitButton = screen.getByRole('button', { name: /sign in/i })
    expect(submitButton).toBeInTheDocument()
  })

  it('shows error message on failed submission', async () => {
    const user = userEvent.setup()
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    )

    await user.type(screen.getByLabelText('Email'), 'test@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    const alert = screen.getByRole('alert')
    expect(alert).toBeInTheDocument()
  })

  it('renders input fields with correct labels', () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    )

    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })
})
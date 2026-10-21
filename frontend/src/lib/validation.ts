import { z } from 'zod'

// Same rules as backend/app/schemas/auth.py, so most mistakes are caught before a request.

export const loginSchema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
})

const newPassword = z
  .string()
  .min(8, 'At least 8 characters')
  .max(128)
  .regex(/[A-Za-z]/, 'Include at least one letter')
  .regex(/\d/, 'Include at least one digit')

const securityAnswer = z.string().trim().min(2, 'At least 2 characters').max(100, 'At most 100 characters')

const passwordsMatch = {
  message: 'Passwords do not match',
  path: ['confirm_password'],
}

export const registerSchema = z
  .object({
    full_name: z.string().trim().min(2, 'Enter your full name').max(120),
    email: z.email('Enter a valid email address'),
    password: newPassword,
    confirm_password: z.string(),
    // Asked at sign-up so the password can be reset without e-mail.
    security_question: z.string().min(1, 'Choose a question'),
    security_answer: securityAnswer,
  })
  .refine((data) => data.password === data.confirm_password, passwordsMatch)

export const nameSchema = z.object({ full_name: z.string().trim().min(2, 'Enter your name').max(120) })

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: newPassword,
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, passwordsMatch)

export const securityQuestionSchema = z.object({
  question: z.string().min(1, 'Choose a question'),
  answer: securityAnswer,
  current_password: z.string().min(1, 'Enter your current password'),
})

export const forgotEmailSchema = z.object({ email: z.email('Enter a valid email address') })

export const resetPasswordSchema = z
  .object({
    answer: z.string().trim().min(1, 'Enter your answer'),
    new_password: newPassword,
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, passwordsMatch)

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
export type NameValues = z.infer<typeof nameSchema>
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>
export type SecurityQuestionValues = z.infer<typeof securityQuestionSchema>
export type ForgotEmailValues = z.infer<typeof forgotEmailSchema>
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>

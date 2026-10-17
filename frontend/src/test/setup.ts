// Adds DOM matchers such as toBeInTheDocument() and toHaveAttribute() to expect().
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Unmount what each test rendered, so tests never see each other's DOM.
afterEach(() => cleanup())

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { getCartSummary } from '../services/homeApi'
import type { CartSummary } from '../types/home'

const emptySummary: CartSummary = { total_items: 0, total_quantity: 0, total_amount: 0, need_confirm_count: 0 }
interface CartSummaryValue {
  summary: CartSummary
  refresh: () => Promise<void>
  sync: (summary: CartSummary) => void
}

const CartSummaryContext = createContext<CartSummaryValue>({ summary: emptySummary, refresh: async () => undefined, sync: () => undefined })

export function CartSummaryProvider({ children }: { children: ReactNode }) {
  const [summary, setSummary] = useState(emptySummary)
  const refresh = useCallback(async () => {
    try { setSummary(await getCartSummary()) } catch { /* the header remains usable with a zero count */ }
  }, [])
  useEffect(() => { void Promise.resolve().then(refresh) }, [refresh])
  return <CartSummaryContext value={{ summary, refresh, sync: setSummary }}>{children}</CartSummaryContext>
}

// The hook intentionally lives beside its provider so the private context cannot be misused.
// eslint-disable-next-line react-refresh/only-export-components
export const useCartSummary = () => useContext(CartSummaryContext)

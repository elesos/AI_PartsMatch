export type ToastTone = 'error' | 'success' | 'info'
export interface ToastMessage { id: string; message: string; tone: ToastTone }

const EVENT_NAME = 'partsmatch:toast'

export const showToast = (message: string, tone: ToastTone = 'info'): void => {
  window.dispatchEvent(new CustomEvent<ToastMessage>(EVENT_NAME, {
    detail: { id: crypto.randomUUID(), message, tone },
  }))
}

export const subscribeToToasts = (listener: (toast: ToastMessage) => void): (() => void) => {
  const handler = (event: Event) => listener((event as CustomEvent<ToastMessage>).detail)
  window.addEventListener(EVENT_NAME, handler)
  return () => window.removeEventListener(EVENT_NAME, handler)
}

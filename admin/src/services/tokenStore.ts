const KEY = 'partsmatch:admin-access:v1'
let memoryToken = sessionStorage.getItem(KEY)
export const getAccessToken = () => memoryToken
export const setAccessToken = (token: string) => { memoryToken = token; sessionStorage.setItem(KEY, token) }
export const clearAccessToken = () => { memoryToken = null; sessionStorage.removeItem(KEY) }

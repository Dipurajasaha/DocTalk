import React, { createContext, useCallback, useContext, useRef, useState } from 'react'

const AssetCacheContext = createContext(null)

export function AssetCacheProvider({ children }) {
  const cacheRef = useRef(new Map())
  const [, setVersion] = useState(0)

  const getAsset = useCallback((key) => cacheRef.current.get(key), [])
  const setAsset = useCallback((key, value) => {
    cacheRef.current.set(key, value)
    setVersion((v) => v + 1)
  }, [])
  const removeAsset = useCallback((key) => {
    cacheRef.current.delete(key)
    setVersion((v) => v + 1)
  }, [])
  const clearCache = useCallback(() => {
    cacheRef.current.clear()
    setVersion((v) => v + 1)
  }, [])

  return (
    <AssetCacheContext.Provider value={{ getAsset, setAsset, removeAsset, clearCache }}>
      {children}
    </AssetCacheContext.Provider>
  )
}

export function useAssetCache() {
  const ctx = useContext(AssetCacheContext)
  if (!ctx) throw new Error('useAssetCache must be used within AssetCacheProvider')
  return ctx
}

export default AssetCacheContext

import React from 'react'
import { NotificationProvider, useNotifications } from './NotificationContext'
import { AssetCacheProvider, useAssetCache } from './AssetCacheContext'

export { NotificationProvider, useNotifications }
export { AssetCacheProvider, useAssetCache }

export function AppProviders({ children }) {
  return (
    <NotificationProvider>
      <AssetCacheProvider>{children}</AssetCacheProvider>
    </NotificationProvider>
  )
}

export default AppProviders

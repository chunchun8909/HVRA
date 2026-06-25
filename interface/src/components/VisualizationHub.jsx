import { useEffect, useMemo, useState } from 'react'

const viewTabs = [
  { key: 'room', label: 'room', title: 'room view' },
  { key: 'components', label: 'room', title: 'room view' },
  { key: 'links', label: 'links', title: 'links view' },
  { key: 'report', label: 'report', title: 'final report' },
]

const fallbackStrategyOptions = [
  { id: 'option_1', label: 'option 1', name: 'waiting for validated option 1' },
  { id: 'option_2', label: 'option 2', name: 'waiting for validated option 2' },
  { id: 'option_3', label: 'option 3', name: 'waiting for validated option 3' },
]

export default function VisualizationHub({
  backendUrl,
  roomRef,
  kgRef,
  reportRef,
  enabledViews = ['room', 'components', 'links', 'report'],
  viewerMode = 'review',
  isLoading = false,
  loadingLabel = '',
  loadingProgress = 0,
  refreshSignal = 0,
}) {
  const firstView = enabledViews[0] || 'room'
  const [activeView, setActiveView] = useState(firstView)
  const [strategyOptions, setStrategyOptions] = useState([])
  const [selectionMode, setSelectionMode] = useState('')
  const visibleTabs = viewTabs.filter((tab) => enabledViews.includes(tab.key))
  const selectedView = enabledViews.includes(activeView) ? activeView : firstView
  const encodedBackendUrl = encodeURIComponent(backendUrl)
  const selectedStrategyIds = useMemo(() => {
    if (viewerMode !== 'review') return []
    if (selectionMode === 'all') return strategyOptions.map((option) => option.id).filter(Boolean)
    return selectionMode ? [selectionMode] : []
  }, [selectionMode, strategyOptions, viewerMode])
  const selectedStrategyParam = selectedStrategyIds.join(',')
  const firstStrategyId = selectedStrategyIds[0] || ''
  const selectedStrategyIndex = strategyOptions.findIndex((option) => option.id === firstStrategyId)
  const componentOptionKey = selectionMode === 'all'
    ? 'all'
    : selectedStrategyIndex >= 0
      ? `option_${selectedStrategyIndex + 1}`
      : firstStrategyId
  const packageParam = firstStrategyId ? encodeURIComponent(firstStrategyId) : ''
  const componentParam = componentOptionKey ? encodeURIComponent(componentOptionKey) : ''
  const strategyQuery = selectedStrategyIds.length
    ? `&strategy_ids=${encodeURIComponent(selectedStrategyParam)}&strategy_id=${packageParam}&package_id=${packageParam}`
    : ''
  const optionQuery = selectedStrategyIds.length
    ? `?strategy_ids=${encodeURIComponent(selectedStrategyParam)}&strategy_id=${packageParam}&package_id=${packageParam}`
    : ''
  const componentQuery = selectedStrategyIds.length
    ? `?strategy_ids=${encodeURIComponent(selectedStrategyParam)}&strategy_id=${componentParam}&package_id=${packageParam}`
    : ''
  const roomSrc = `${backendUrl}/static-views/spatial/room_3d_view.html?viewer_mode=${viewerMode}&api_base=${encodedBackendUrl}${strategyQuery}&v=${refreshSignal}`
  const componentSrc = `${backendUrl}/static-views/spatial/room_3d_full_texture_component_check.html${componentQuery}${componentQuery ? "&" : "?"}v=${refreshSignal}`
  const kgSrc = `${backendUrl}/static-views/kg/kg_view.html${optionQuery}${optionQuery ? "&" : "?"}v=${refreshSignal}`
  const reportSrc = `${backendUrl}/static-views/final_report_view.html${optionQuery}${optionQuery ? "&" : "?"}v=${refreshSignal}`

  useEffect(() => {
    setActiveView(firstView)
  }, [firstView, viewerMode])

  useEffect(() => {
    if (viewerMode !== 'review') {
      setStrategyOptions([])
      setSelectionMode('')
      return
    }

    fetch(`${backendUrl}/api/strategy-options`)
      .then((response) => (response.ok ? response.json() : { options: [] }))
      .then((payload) => {
        const options = payload.options?.length ? payload.options : fallbackStrategyOptions
        setStrategyOptions(options)
        setSelectionMode((current) => {
          if (current === 'all') return 'all'
          return options.some((option) => option.id === current) ? current : options[0]?.id || ''
        })
      })
      .catch(() => {
        setStrategyOptions(fallbackStrategyOptions)
        setSelectionMode((current) => current || fallbackStrategyOptions[0].id)
      })
  }, [backendUrl, viewerMode])

  const frameClass = (key) => `absolute inset-0 h-full w-full border-0 ${selectedView === key ? 'z-10 opacity-100' : 'z-0 pointer-events-none opacity-0'}`

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-surface-secondary">
      <div className="type-level-1 flex items-center justify-between gap-3 border-b border-DEFAULT px-5 py-3">
        <div className="flex min-w-0 items-center gap-2">
          {strategyOptions.length > 0 && !isLoading ? (
            <>
              {strategyOptions.slice(0, 3).map((option) => (
                <button
                  key={option.id}
                  type="button"
                  aria-pressed={selectionMode === option.id}
                  title={`${option.name}${option.status ? ` | ${option.status}` : ''}${option.confidence ? ` | ${option.confidence}` : ''}`}
                  className={`type-level-3 rounded-sm border px-3 py-2 ${
                    selectionMode === option.id
                      ? 'border-strong bg-surface-primary text-ink-primary'
                      : 'border-DEFAULT bg-surface-secondary text-ink-tertiary'
                  }`}
                  onClick={() => setSelectionMode(option.id)}
                >
                  {option.label}
                </button>
              ))}
              <button
                type="button"
                aria-pressed={selectionMode === 'all'}
                title="show all three retrofit options as a combined visual review"
                className={`type-level-3 rounded-sm border px-3 py-2 ${
                  selectionMode === 'all'
                    ? 'border-strong bg-surface-primary text-ink-primary'
                    : 'border-DEFAULT bg-surface-secondary text-ink-tertiary'
                }`}
                onClick={() => setSelectionMode('all')}
              >
                all
              </button>
            </>
          ) : (
            <span>{isLoading ? loadingLabel || 'working' : viewTabs.find((tab) => tab.key === selectedView)?.title}</span>
          )}
        </div>
        {visibleTabs.length > 1 && !isLoading ? (
          <div className="flex gap-2">
            {visibleTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={`type-level-3 rounded-sm border px-3 py-2 ${
                  selectedView === tab.key
                    ? 'border-strong bg-surface-primary text-ink-primary'
                    : 'border-DEFAULT bg-surface-secondary text-ink-tertiary'
                }`}
                onClick={() => setActiveView(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-surface-primary">
        {enabledViews.includes('room') ? <iframe key={roomSrc} ref={roomRef} src={roomSrc} title="room view" className={frameClass('room')} /> : null}
        {enabledViews.includes('components') ? <iframe key={componentSrc} src={componentSrc} title="component room view" className={frameClass('components')} /> : null}
        {enabledViews.includes('links') ? <iframe key={kgSrc} ref={kgRef} src={kgSrc} title="links view" className={frameClass('links')} /> : null}
        {enabledViews.includes('report') ? <iframe key={reportSrc} ref={reportRef} src={reportSrc} title="final report" className={frameClass('report')} /> : null}
      </div>

      {isLoading ? (
        <div className="absolute inset-x-0 bottom-0 border-t border-DEFAULT bg-surface-primary/95 px-5 py-4">
          <div className="mb-2 flex items-center justify-between type-level-3">
            <span>{loadingLabel || 'working'}</span>
            <span>{Math.round(loadingProgress)}%</span>
          </div>
          <div className="h-1 w-full bg-surface-tertiary">
            <div className="h-full bg-accent transition-[width] duration-300" style={{ width: `${Math.min(100, Math.max(0, loadingProgress))}%` }} />
          </div>
        </div>
      ) : null}
    </div>
  )
}








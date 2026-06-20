export default function InstructionBanner({ tasks, currentStage }) {
  return (
    <div className="border-b border-DEFAULT bg-surface-primary px-5 py-2">
      <div className="flex items-center justify-between gap-4">
        <p className="type-level-1">status</p>
        <span className="type-level-3 rounded-pill border border-DEFAULT bg-surface-secondary px-3 py-1">
          {currentStage}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {tasks.map((task) => (
          <div key={task.key} className="flex items-center gap-2">
            <span
              className={`type-level-3 inline-flex h-3 w-3 items-center justify-center rounded-full ${
                task.done
                  ? 'border border-accent-border bg-accent-bg text-accent'
                  : 'border border-strong bg-surface-primary text-transparent'
              }`}
            >
              {task.done ? '' : ''}
            </span>
            <p className={`type-level-3 ${task.done ? 'text-ink-secondary' : 'text-ink-primary'}`}>
              {task.label}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

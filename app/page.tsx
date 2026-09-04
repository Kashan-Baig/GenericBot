
'use client'

import { useEffect, useRef, useState } from 'react'

import {
  Activity,
  ArrowLeft,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileJson,
  Loader2,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Save,
  Search,
  Send,
  Settings,
  TriangleAlert,
  Users,
  Workflow,
  X,
  Zap,
} from 'lucide-react'

import { FlowCanvas } from '@/flow/FlowCanvas'
import { NodeConfigPanel } from '@/flow/NodeConfigPanel'

import {
  NODE_META,
  createNode,
  emptyFlow,
  flowToJson,
  navItems,
  nodeIcons,
  nodeToneClasses,
  nodeTypeList,
  setFlowStatus,
  type Flow,
  type FlowNode,
} from '@/types/flow'

import { flowApi, chatApi } from '@/services/api'


// ============================================================
// ICON MAP
// ============================================================

const iconMap: Record<string, any> = {
  Dashboard: Activity,
  Flows: Workflow,
  Conversations: MessageSquare,
  Customers: Users,
  Automations: Zap,
  Appointments: CalendarDays,
  Settings,
}


// ============================================================
// SIDEBAR
// ============================================================

function Sidebar({
  current,
  setCurrent,
}: {
  current: string
  setCurrent: (value: string) => void
}) {
  return (
    <aside className="sidebar">

      <div className="brand">
        <span className="brand-mark">✦</span>
        <span>Flowcraft</span>
      </div>

      <div className="workspace">
        <div>
          <small>Workspace</small>
          <strong>My Workspace</strong>
        </div>

        <ChevronDown
          size={14}
          color="#94a3b8"
        />
      </div>

      <nav className="nav">

        <div className="nav-section">
          Workspace
        </div>

        {navItems.slice(0, 3).map((item) => {
          const Icon = iconMap[item]

          return (
            <button
              key={item}
              type="button"
              className={current === item ? 'active' : ''}
              onClick={() => setCurrent(item)}
            >
              {Icon && <Icon size={17} />}
              <span>{item}</span>
            </button>
          )
        })}

        <div className="nav-section">
          Manage
        </div>

        {navItems.slice(3).map((item) => {
          const Icon = iconMap[item]

          return (
            <button
              key={item}
              type="button"
              className={current === item ? 'active' : ''}
              onClick={() => setCurrent(item)}
            >
              {Icon && <Icon size={17} />}
              <span>{item}</span>
            </button>
          )
        })}

      </nav>

      <div className="sidebar-bottom">
        <button
          type="button"
          className="nav"
        >
          <span className="nav-section">
            Need help?
          </span>

          <span className="nav">
            <span>Visit documentation</span>
          </span>
        </button>
      </div>

    </aside>
  )
}


// ============================================================
// TOPBAR
// ============================================================

function Topbar({
  current,
  onMenu,
}: {
  current: string
  onMenu: () => void
}) {
  return (
    <header className="topbar">

      <div className="breadcrumb">

        <button
          type="button"
          className="icon-button mobile-only"
          onClick={onMenu}
          aria-label="Open menu"
        >
          <Menu size={18} />
        </button>

        <span>Workspace</span>

        <ChevronRight size={13} />

        <strong>{current}</strong>

      </div>

      <div className="top-actions">

        <div className="search-box">
          <Search size={14} />

          <span>Search</span>

          <span
            style={{
              marginLeft: 16,
              border: '1px solid #dbe2ec',
              borderRadius: 4,
              padding: '1px 5px',
              fontSize: 10,
            }}
          >
            ⌘ K
          </span>
        </div>

        <button
          type="button"
          className="icon-button"
          aria-label="Help"
        >
          <CircleHelp size={17} />
        </button>

      </div>

    </header>
  )
}


// ============================================================
// DASHBOARD
// ============================================================

function Dashboard({
  flows,
  flowsLoading,
  flowsError,
  onNavigate,
  onCreateFlow,
}: {
  flows: Flow[]
  flowsLoading: boolean
  flowsError: string | null
  onNavigate: (view: string) => void
  onCreateFlow: () => void
}) {

  const activeFlows = flows.filter(
    (flow) => flow.status === 'active'
  ).length

  const stats = [
    {
      label: 'Active flows',
      value: flowsLoading
        ? '—'
        : flowsError
          ? 'N/A'
          : String(activeFlows),
      trend: flowsError
        ? 'Unable to load'
        : 'From /flows',
    },

    {
      label: 'Conversations',
      value: 'N/A',
      trend: 'No /conversations endpoint yet',
    },

    {
      label: 'Avg. response time',
      value: 'N/A',
      trend: 'No metrics endpoint yet',
    },

    {
      label: 'Leads captured',
      value: 'N/A',
      trend: 'No metrics endpoint yet',
    },
  ]

  return (
    <div className="content">

      <div className="page-title">

        <div>
          <h1>Dashboard</h1>

          <p>
            Here’s what’s happening across your workspace today.
          </p>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={onCreateFlow}
        >
          <Plus size={16} />
          Create flow
        </button>

      </div>

      <div className="stat-grid">

        {stats.map((stat) => (
          <div
            className="stat-card"
            key={stat.label}
          >
            <div className="label">
              {stat.label}
            </div>

            <div className="value">
              {stat.value}
            </div>

            <div className="trend">
              {stat.trend}
            </div>
          </div>
        ))}

      </div>

      <div className="dashboard-grid">

        <div className="panel">

          <div className="panel-header">

            <h2>
              Recent conversations
            </h2>

            <button
              type="button"
              className="subtle-button"
              onClick={() => onNavigate('Conversations')}
            >
              View all
              <ChevronRight size={14} />
            </button>

          </div>

          <div
            style={{
              padding: '40px 20px',
              textAlign: 'center',
              color: '#94a3b8',
            }}
          >
            <p
              style={{
                margin: 0,
                color: '#475569',
                fontWeight: 600,
                fontSize: 13,
              }}
            >
              No conversation data available
            </p>

            <small>
              Waiting on a GET /conversations endpoint from the backend.
            </small>
          </div>

        </div>


        <div className="panel">

          <div className="panel-header">
            <h2>Activity</h2>
            <span>—</span>
          </div>

          <div
            style={{
              padding: '40px 20px',
              textAlign: 'center',
              color: '#94a3b8',
            }}
          >
            <p
              style={{
                margin: 0,
                color: '#475569',
                fontWeight: 600,
                fontSize: 13,
              }}
            >
              No activity feed available
            </p>

            <small>
              Waiting on an activity/audit-log endpoint from the backend.
            </small>
          </div>

        </div>

      </div>

    </div>
  )
}


// ============================================================
// FLOWS PAGE
// ============================================================

function Flows({
  flows,
  loading,
  error,
  onOpen,
  onCreate,
  onRetry,
  onRename,
  onDelete,
}: {
  flows: Flow[]
  loading: boolean
  error: string | null
  onOpen: (flow: Flow) => void
  onCreate: () => void
  onRetry: () => void
  onRename: (flow: Flow, newName: string) => Promise<void>
  onDelete: (flow: Flow) => Promise<void>
}) {

  // ==========================================================
  // ACTION MENU / RENAME STATE
  // ==========================================================

  const [openMenu, setOpenMenu] =
    useState<string | null>(null)

  const [renameFlow, setRenameFlow] =
    useState<Flow | null>(null)

  const [renameValue, setRenameValue] =
    useState('')

  const [actionLoading, setActionLoading] =
    useState(false)


  // ==========================================================
  // RENAME
  // ==========================================================

  const handleRename = async () => {

    if (!renameFlow) {
      return
    }

    const name =
      renameValue.trim()

    if (!name) {
      return
    }

    setActionLoading(true)

    try {

      await onRename(
        renameFlow,
        name
      )

      setRenameFlow(null)
      setRenameValue('')
      setOpenMenu(null)

    } catch (error) {

      console.error(
        'Failed to rename flow:',
        error
      )

      alert(
        error instanceof Error
          ? error.message
          : 'Failed to rename flow'
      )

    } finally {

      setActionLoading(false)

    }
  }


  // ==========================================================
  // DELETE
  // ==========================================================

  const handleDelete = async (
    flow: Flow
  ) => {

    const confirmed =
      window.confirm(
        `Are you sure you want to delete "${flow.name}"?\n\nThis action cannot be undone.`
      )

    if (!confirmed) {
      return
    }

    setActionLoading(true)

    try {

      await onDelete(flow)

      setOpenMenu(null)

    } catch (error) {

      console.error(
        'Failed to delete flow:',
        error
      )

      alert(
        error instanceof Error
          ? error.message
          : 'Failed to delete flow'
      )

    } finally {

      setActionLoading(false)

    }
  }


  return (
    <div className="content">

      <div className="page-title">

        <div>
          <h1>Flows</h1>

          <p>
            Design and manage your automated conversations.
          </p>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={onCreate}
        >
          <Plus size={16} />
          Create flow
        </button>

      </div>


      <div
        style={{
          display: 'flex',
          gap: 10,
          marginBottom: 20,
        }}
      >

        <div
          className="search-box"
          style={{
            width: 270,
            background: '#fff',
          }}
        >
          <Search size={14} />
          Search flows
        </div>

        <button
          type="button"
          className="secondary-button"
        >
          All flows
          <ChevronDown size={14} />
        </button>

      </div>


      {/* ======================================================
          LOADING
          ====================================================== */}

      {loading && (
        <div
          className="panel"
          style={{
            padding: 40,
            textAlign: 'center',
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
          }}
        >
          <Loader2
            size={16}
            className="spin"
          />

          Loading flows...
        </div>
      )}


      {/* ======================================================
          ERROR
          ====================================================== */}

      {!loading && error && (
        <div
          className="panel"
          style={{
            padding: 40,
            textAlign: 'center',
            color: '#b91c1c',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 10,
          }}
        >

          <TriangleAlert size={20} />

          <p style={{ margin: 0 }}>
            Unable to load flows.
            Make sure the backend is running.
          </p>

          <button
            type="button"
            className="secondary-button"
            onClick={onRetry}
          >
            Try again
          </button>

        </div>
      )}


      {/* ======================================================
          EMPTY
          ====================================================== */}

      {!loading &&
        !error &&
        flows.length === 0 && (
          <div
            className="panel"
            style={{
              padding: 40,
              textAlign: 'center',
              color: '#64748b',
            }}
          >
            <p style={{ margin: 0 }}>
              No flows created yet.
            </p>

            <small>
              Click “Create flow” to build your first automated conversation.
            </small>
          </div>
        )}


      {/* ======================================================
          FLOW LIST
          ====================================================== */}

      {!loading &&
        !error &&
        flows.length > 0 && (

          <div className="flow-list">

            {flows.map((flow) => (

              <div
                className="flow-card"
                key={flow.flow_id}
              >

                {/* ==================================================
                    FLOW CARD HEADER
                    ================================================== */}

                <div
                  className="flow-card-head"
                  style={{
                    position: 'relative',
                  }}
                >

                  <div className="flow-icon">
                    <Workflow size={18} />
                  </div>


                  {/* ==================================================
                      THREE DOT MENU
                      ================================================== */}

                  <div
                    style={{
                      position: 'relative',
                    }}
                  >

                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`Actions for ${flow.name}`}
                      title="Flow actions"
                      onClick={(event) => {

                        event.stopPropagation()

                        setOpenMenu(
                          openMenu === flow.flow_id
                            ? null
                            : flow.flow_id
                        )

                      }}
                    >
                      <MoreHorizontal size={17} />
                    </button>


                    {/* ==================================================
                        ACTION DROPDOWN
                        ================================================== */}

                    {openMenu === flow.flow_id && (

                      <div
                        style={{
                          position: 'absolute',
                          top: 'calc(100% + 6px)',
                          right: 0,
                          width: 155,
                          background: '#fff',
                          border: '1px solid #e2e8f0',
                          borderRadius: 8,
                          boxShadow:
                            '0 8px 25px rgba(15, 23, 42, 0.12)',
                          padding: 5,
                          zIndex: 100,
                        }}
                        onClick={(event) => {
                          event.stopPropagation()
                        }}
                      >

                        {/* RENAME */}

                        <button
                          type="button"
                          disabled={actionLoading}
                          onClick={() => {

                            setRenameFlow(flow)

                            setRenameValue(
                              flow.name
                            )

                            setOpenMenu(null)

                          }}
                          style={{
                            width: '100%',
                            border: 0,
                            background: 'transparent',
                            padding: '9px 10px',
                            textAlign: 'left',
                            borderRadius: 6,
                            cursor: actionLoading
                              ? 'not-allowed'
                              : 'pointer',
                            fontSize: 13,
                            color: '#334155',
                          }}
                          onMouseEnter={(event) => {
                            event.currentTarget.style.background =
                              '#f8fafc'
                          }}
                          onMouseLeave={(event) => {
                            event.currentTarget.style.background =
                              'transparent'
                          }}
                        >
                          Rename
                        </button>


                        {/* DELETE */}

                        <button
                          type="button"
                          disabled={actionLoading}
                          onClick={() =>
                            handleDelete(flow)
                          }
                          style={{
                            width: '100%',
                            border: 0,
                            background: 'transparent',
                            padding: '9px 10px',
                            textAlign: 'left',
                            borderRadius: 6,
                            cursor: actionLoading
                              ? 'not-allowed'
                              : 'pointer',
                            fontSize: 13,
                            color: '#dc2626',
                          }}
                          onMouseEnter={(event) => {
                            event.currentTarget.style.background =
                              '#fef2f2'
                          }}
                          onMouseLeave={(event) => {
                            event.currentTarget.style.background =
                              'transparent'
                          }}
                        >
                          Delete
                        </button>

                      </div>

                    )}

                  </div>

                </div>


                {/* ==================================================
                    FLOW INFORMATION
                    ================================================== */}

                <div>

                  <h3>
                    {flow.name}
                  </h3>

                  <p>
                    {flow.description ||
                      'Build an automated conversation with the visual editor.'}
                  </p>

                </div>


                {/* ==================================================
                    FOOTER
                    ================================================== */}

                <div className="flow-card-footer">

                  <div className="flow-meta">

                    <span>
                      {flow.nodes?.length ?? 0} nodes
                    </span>

                    <span>·</span>

                    <span>
                      {flow.updatedAt || 'Not saved'}
                    </span>

                  </div>


                  <span
                    className={`status ${flow.status === 'active'
                        ? 'active'
                        : 'draft'
                      }`}
                  >
                    {flow.status === 'active'
                      ? 'Active'
                      : 'Draft'}
                  </span>

                </div>


                {/* ==================================================
                    OPEN BUILDER
                    ================================================== */}

                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onOpen(flow)}
                >
                  Open builder
                  <ChevronRight size={14} />
                </button>

              </div>

            ))}

          </div>

        )}


      {/* ======================================================
          RENAME MODAL
          ====================================================== */}

      {renameFlow && (

        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 200,
            padding: 16,
          }}
          onClick={() => {

            if (!actionLoading) {
              setRenameFlow(null)
            }

          }}
        >

          <div
            className="panel"
            style={{
              width: 400,
              maxWidth: 'calc(100vw - 32px)',
              padding: 22,
              background: '#fff',
            }}
            onClick={(event) => {
              event.stopPropagation()
            }}
          >

            <div className="panel-header">

              <div>

                <h2
                  style={{
                    margin: 0,
                    fontSize: 16,
                  }}
                >
                  Rename flow
                </h2>

                <p
                  style={{
                    margin: '5px 0 0',
                    fontSize: 12,
                    color: '#64748b',
                  }}
                >
                  Choose a new name for this flow.
                </p>

              </div>


              <button
                type="button"
                className="icon-button"
                onClick={() => {
                  setRenameFlow(null)
                }}
                disabled={actionLoading}
                aria-label="Close rename dialog"
              >
                <X size={17} />
              </button>

            </div>


            <input
              autoFocus
              value={renameValue}
              onChange={(event) =>
                setRenameValue(
                  event.target.value
                )
              }
              onKeyDown={(event) => {

                if (
                  event.key === 'Enter'
                ) {
                  event.preventDefault()
                  handleRename()
                }

                if (
                  event.key === 'Escape'
                ) {
                  setRenameFlow(null)
                }

              }}
              placeholder="Flow name"
              disabled={actionLoading}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                border: '1px solid #cbd5e1',
                borderRadius: 7,
                padding: '10px 11px',
                fontSize: 13,
                marginTop: 18,
                outline: 'none',
              }}
            />


            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 8,
                marginTop: 15,
              }}
            >

              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  setRenameFlow(null)
                }
                disabled={actionLoading}
              >
                Cancel
              </button>


              <button
                type="button"
                className="primary-button"
                onClick={handleRename}
                disabled={
                  actionLoading ||
                  !renameValue.trim()
                }
              >

                {actionLoading && (
                  <Loader2
                    size={14}
                    className="spin"
                  />
                )}

                {actionLoading
                  ? 'Renaming...'
                  : 'Rename'}

              </button>

            </div>

          </div>

        </div>

      )}

    </div>
  )
}


// ============================================================
// TEST CHAT
// ============================================================

function TestChatPanel({
  flow,
  onClose,
}: {
  flow: Flow
  onClose: () => void
}) {

  type ChatMessage = {
    role: 'user' | 'bot'
    text: string
  }

  const [conversationId] = useState(
    () =>
      `conv-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2, 8)}`
  )

  const [messages, setMessages] =
    useState<ChatMessage[]>([])

  const [input, setInput] =
    useState('')

  const [sending, setSending] =
    useState(false)

  const [error, setError] =
    useState<string | null>(null)


  const localNodeIdRef =
    useRef<string | null>(null)

  const localVariablesRef =
    useRef<Record<string, unknown>>({})


  const nodes =
    Array.isArray(flow.nodes)
      ? flow.nodes
      : []

  const edges =
    Array.isArray((flow as any).edges)
      ? (flow as any).edges
      : []


  // ==========================================================
  // NODE HELPERS
  // ==========================================================

  const getNode = (
    id: string | null | undefined
  ) => {

    if (!id) {
      return undefined
    }

    return nodes.find(
      (node) => node.id === id
    )
  }


  const getNextNode = (
    nodeId: string
  ) => {

    const edge =
      edges.find(
        (item: any) =>
          item.source === nodeId
      )

    return getNode(
      edge?.target
    )
  }


  // ==========================================================
  // VARIABLE INTERPOLATION
  // ==========================================================

  const interpolateVariables = (
    text: string
  ) => {

    if (!text) {
      return ''
    }

    return text.replace(
      /\{\{\s*([^}]+?)\s*\}\}/g,
      (_, key: string) => {

        const value =
          localVariablesRef.current[
          key.trim()
          ]

        return value === undefined ||
          value === null
          ? ''
          : String(value)
      }
    )
  }


  // ==========================================================
  // LOCAL FLOW EXECUTOR
  // ==========================================================

  const executeLocalFlow = (
    userText: string
  ) => {

    let current =
      getNode(
        localNodeIdRef.current
      )


    if (!current) {

      current =
        nodes.find(
          (node) =>
            node.type === 'start'
        )
    }


    if (!current) {

      return {
        response: '',
        status: 'error',
        currentNode: null as string | null,
      }
    }


    const output: string[] = []

    let guard = 0


    // ========================================================
    // INPUT NODE
    // ========================================================

    if (current.type === 'input') {

      const variable =
        String(
          current.config?.variable || ''
        ).trim()


      if (variable) {

        localVariablesRef.current = {
          ...localVariablesRef.current,

          [variable]:
            userText,
        }

      }


      current =
        getNextNode(
          current.id
        )
    }


    // ========================================================
    // EXECUTION LOOP
    // ========================================================

    while (
      current &&
      guard <
      Math.max(
        nodes.length * 3,
        10
      )
    ) {

      guard += 1


      // ======================================================
      // START
      // ======================================================

      if (
        current.type === 'start'
      ) {

        current =
          getNextNode(
            current.id
          )

        continue
      }


      // ======================================================
      // MESSAGE
      // ======================================================

      if (
        current.type === 'message'
      ) {

        const rawText =
          String(
            current.config?.text ||
            ''
          ).trim()


        const text =
          interpolateVariables(
            rawText
          )


        if (text) {
          output.push(text)
        }


        const next =
          getNextNode(
            current.id
          )


        if (
          next?.type === 'input'
        ) {

          localNodeIdRef.current =
            next.id

          break
        }


        current = next

        continue
      }


      // ======================================================
      // INPUT
      // ======================================================

      if (
        current.type === 'input'
      ) {

        const prompt =
          interpolateVariables(
            String(
              current.config?.text ||
              ''
            ).trim()
          )


        if (
          prompt &&
          output.length === 0
        ) {

          output.push(prompt)
        }


        localNodeIdRef.current =
          current.id

        break
      }


      // ======================================================
      // END
      // ======================================================

      if (
        current.type === 'end'
      ) {

        localNodeIdRef.current =
          current.id

        break
      }


      // ======================================================
      // UNKNOWN
      // ======================================================

      current =
        getNextNode(
          current.id
        )
    }


    return {
      response:
        output.join('\n\n'),

      status:
        current?.type === 'end'
          ? 'completed'
          : 'running',

      currentNode:
        localNodeIdRef.current,
    }
  }


  // ==========================================================
  // RESET
  // ==========================================================

  const resetLocalExecution = () => {

    localNodeIdRef.current =
      null

    localVariablesRef.current =
      {}
  }


  // ==========================================================
  // SEND MESSAGE
  // ==========================================================

  const send = async () => {

    const text =
      input.trim()


    if (
      !text ||
      sending
    ) {
      return
    }


    setMessages(
      (current) => [
        ...current,

        {
          role: 'user',
          text,
        },
      ]
    )


    setInput('')
    setSending(true)
    setError(null)


    try {

      const result: any =
        await chatApi.sendMessage({

          conversation_id:
            conversationId,

          flow_id:
            flow.flow_id,

          message:
            text,

        })


      const currentNodeId =
        result?.current_node ||
        result?.currentNode ||
        result?.node_id ||
        result?.current_node_id ||
        null


      const currentNode =
        getNode(
          currentNodeId
        )


      if (
        currentNode?.type === 'input'
      ) {

        localNodeIdRef.current =
          currentNode.id
      }


      const backendResponse =
        String(
          result?.response ||
          result?.message ||
          ''
        ).trim()


      if (
        backendResponse
      ) {

        setMessages(
          (current) => [
            ...current,

            {
              role: 'bot',
              text:
                backendResponse,
            },
          ]
        )

        return
      }


      const localResult =
        executeLocalFlow(
          text
        )


      if (
        localResult.response
      ) {

        setMessages(
          (current) => [
            ...current,

            {
              role: 'bot',
              text:
                localResult.response,
            },
          ]
        )

      } else {

        setError(
          `The backend returned no message. Current node: ${currentNodeId ||
          localResult.currentNode ||
          'unknown'
          }. Check the backend graph execution.`
        )
      }


    } catch (
    requestError: any
    ) {

      console.error(
        'Chat request failed:',
        requestError
      )


      const localResult =
        executeLocalFlow(
          text
        )


      if (
        localResult.response
      ) {

        setMessages(
          (current) => [
            ...current,

            {
              role: 'bot',
              text:
                localResult.response,
            },
          ]
        )


        setError(
          'Backend /chat is unavailable. Showing the saved flow in local Test Chat mode.'
        )

      } else {

        setError(
          'Unable to reach /chat, and the saved flow could not produce a message.'
        )
      }


    } finally {

      setSending(false)

    }
  }


  // ==========================================================
  // NEW TEST
  // ==========================================================

  const startNewTest = () => {

    resetLocalExecution()

    setMessages([])

    setInput('')

    setError(null)
  }


  // ==========================================================
  // UI
  // ==========================================================

  return (
    <aside
      className="config-panel"
      style={{
        width: 340,
        display: 'flex',
        flexDirection: 'column',
      }}
    >

      <div className="config-header">

        <div>

          <div
            className="eyebrow"
            style={{
              background: '#eef0ff',
              color: '#4338ca',
            }}
          >
            Test chat
          </div>

          <h2>
            {flow.name}
          </h2>

        </div>


        <div
          style={{
            display: 'flex',
            gap: 6,
          }}
        >

          <button
            type="button"
            className="icon-button"
            onClick={startNewTest}
            aria-label="Reset test chat"
            title="Reset test chat"
          >
            <span
              style={{
                fontSize: 14,
              }}
            >
              ↻
            </span>
          </button>


          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close test chat"
          >
            <X size={18} />
          </button>

        </div>

      </div>


      <div
        className="config-body"
        style={{
          flex: 1,
          gap: 10,
          overflowY: 'auto',
        }}
      >

        {messages.length === 0 && (
          <div className="config-note">
            Send a message to test the saved flow.
            Messages follow the nodes and edges in this builder.
          </div>
        )}


        {messages.map(
          (message, index) => (

            <div
              key={`${conversationId}-${index}`}
              style={{
                display: 'flex',
                flexDirection:
                  message.role === 'user'
                    ? 'row-reverse'
                    : 'row',
                alignItems: 'flex-end',
                gap: 8,
              }}
            >

              {/* Bot avatar */}
              {message.role === 'bot' && (
                <div
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #818cf8, #4f46e5)',
                    display: 'grid',
                    placeItems: 'center',
                    fontSize: 12,
                    flexShrink: 0,
                    marginBottom: 2,
                  }}
                >
                  ✦
                </div>
              )}

              <div
                style={{
                  background:
                    message.role === 'user'
                      ? 'linear-gradient(135deg, #6366f1, #4f46e5)'
                      : '#f1f5f9',

                  color:
                    message.role === 'user'
                      ? '#ffffff'
                      : '#334155',

                  padding: '10px 13px',

                  borderRadius:
                    message.role === 'user'
                      ? '12px 12px 3px 12px'
                      : '12px 12px 12px 3px',

                  fontSize: 13,

                  maxWidth: '82%',

                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.55,

                  boxShadow:
                    message.role === 'user'
                      ? '0 2px 8px rgba(99,102,241,.35)'
                      : '0 1px 3px rgba(15,23,42,.08)',
                }}
              >
                {message.text}
              </div>

            </div>

          )
        )}


        {sending && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              paddingLeft: 34,
            }}
          >
            <div
              style={{
                display: 'flex',
                gap: 4,
                alignItems: 'center',
              }}
            >
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: '#94a3b8',
                    animation: `bounce 1.2s ease-in-out ${i * 0.18}s infinite`,
                  }}
                />
              ))}
            </div>
          </div>
        )}


        {error && (
          <div
            style={{
              color: '#b91c1c',
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: 8,
              padding: '8px 10px',
              fontSize: 12,
              lineHeight: 1.45,
            }}
          >
            {error}
          </div>
        )}

      </div>


      <div
        className="config-footer"
        style={{
          justifyContent:
            'space-between',

          gap: 8,
        }}
      >

        <input
          value={input}
          onChange={(e) =>
            setInput(
              e.target.value
            )
          }

          onKeyDown={(e) => {

            if (
              e.key === 'Enter' &&
              !e.shiftKey
            ) {

              e.preventDefault()

              send()
            }
          }}

          placeholder="Type a message..."

          disabled={sending}

          style={{
            flex: 1,
            minWidth: 0,
            border:
              '1px solid var(--border)',
            borderRadius: 7,
            padding:
              '9px 10px',
            fontSize: 13,
          }}
        />


        <button
          type="button"
          className="primary-button"
          onClick={send}
          disabled={
            sending ||
            !input.trim()
          }

          aria-label="Send message"
        >

          {sending ? (

            <Loader2
              size={15}
              className="spin"
            />

          ) : (

            <Send size={15} />

          )}

        </button>

      </div>

    </aside>
  )
}


// ============================================================
// FLOW BUILDER
// ============================================================

function Builder({
  flow,
  setFlow,
  onBack,
  onSave,
  saving,
  saveError,
}: {
  flow: Flow
  setFlow: (flow: Flow) => void
  onBack: () => void
  onSave: (flow: Flow) => void
  saving: boolean
  saveError: string | null
}) {

  const [selected, setSelected] =
    useState<string | null>(null)

  const [jsonOpen, setJsonOpen] =
    useState(false)

  const [testOpen, setTestOpen] =
    useState(false)

  const [draggingType, setDraggingType] =
    useState<string | null>(null)


  const selectedNode =
    flow.nodes?.find(
      (node) =>
        node.id === selected
    )


  // ==========================================================
  // UPDATE NODE
  // ==========================================================

  const updateNode = (
    config: Partial<FlowNode['config']>
  ) => {

    if (!selectedNode) {
      return
    }


    const updatedNodes =
      flow.nodes.map(
        (node) => {

          if (
            node.id !==
            selectedNode.id
          ) {
            return node
          }


          return {
            ...node,

            config: {
              ...node.config,
              ...config,
            },
          }
        }
      )


    const nextFlow = {
      ...flow,
      nodes: updatedNodes,
    }

    setFlow(nextFlow)

    // WhatsApp credentials/provider must be persisted before Test Chat calls
    // the backend by flow_id. Auto-save this node so the backend never runs
    // an older Meta-only copy of the flow after the panel is saved.
    if (selectedNode.type === 'whatsapp') {
      flowApi.save(nextFlow)
        .then((saved) => {
          setEditingFlow(saved)
          setSaveError(null)
        })
        .catch((err) => {
          console.error('Failed to auto-save WhatsApp node:', err)
          setSaveError(err?.message || 'Failed to save WhatsApp node')
        })
    }
  }


  // ==========================================================
  // ADD NODE
  // ==========================================================

  const addNode = (
    type: any
  ) => {

    const newNode =
      createNode(
        type,
        flow.nodes.length
      )


    const updatedFlow: Flow = {
      ...flow,
      nodes: [...flow.nodes, newNode],
      edges: [...flow.edges],
    }

    const outgoingSources = new Set(flow.edges.map((edge) => edge.source))
    const previousNode = [...flow.nodes].reverse().find((candidate) => candidate.type !== 'end' && !outgoingSources.has(candidate.id))
    if (previousNode && newNode.type !== 'start') {
      updatedFlow.edges.push({
        id: `edge-${previousNode.id}-${newNode.id}-${Date.now()}`,
        source: previousNode.id,
        target: newNode.id,
      })
    }

    setFlow(updatedFlow)


    setSelected(
      newNode.id
    )
  }


  // ==========================================================
  // DRAG START
  // ==========================================================

  const handleDragStart = (
    event: React.DragEvent<HTMLButtonElement>,
    type: string
  ) => {

    setDraggingType(type)

    event.dataTransfer.setData(
      'application/flow-node',
      type
    )

    event.dataTransfer.effectAllowed =
      'copy'
  }


  // ==========================================================
  // DRAG END
  // ==========================================================

  const handleDragEnd = () => {

    setDraggingType(null)

  }


  // ==========================================================
  // CANVAS DRAG OVER
  // ==========================================================

  const handleCanvasDragOver = (
    event: React.DragEvent<HTMLDivElement>
  ) => {

    event.preventDefault()

    event.dataTransfer.dropEffect =
      'copy'
  }


  // ==========================================================
  // CANVAS DROP
  // ==========================================================

  const handleCanvasDrop = (
    event: React.DragEvent<HTMLDivElement>
  ) => {

    event.preventDefault()


    const type =
      event.dataTransfer.getData(
        'application/flow-node'
      )


    if (!type) {
      return
    }


    addNode(type)


    event.dataTransfer.clearData(
      'application/flow-node'
    )


    setDraggingType(null)
  }


  // ==========================================================
  // REMOVE SELECTED NODE
  // ==========================================================

  const removeSelectedNode = () => {

    if (!selectedNode) {
      return
    }


    if (
      selectedNode.type === 'start'
    ) {
      return
    }


    const updatedNodes =
      flow.nodes.filter(
        (node) =>
          node.id !==
          selectedNode.id
      )


    setFlow({
      ...flow,
      nodes:
        updatedNodes,
    })


    setSelected(null)
  }


  // ==========================================================
  // BUILDER UI
  // ==========================================================

  return (
    <div className="builder-page">

      <div className="builder-toolbar">

        <div className="builder-title">

          <button
            type="button"
            className="icon-button"
            onClick={onBack}
            aria-label="Back to flows"
          >
            <ArrowLeft size={17} />
          </button>


          <div>

            <h1>
              {flow.name}
            </h1>


            <span
              className={`status ${flow.status === 'active'
                  ? 'active'
                  : 'draft'
                }`}
            >
              {flow.status === 'active'
                ? 'Active'
                : 'Draft'}
            </span>

          </div>

        </div>


        <div className="builder-actions">

          {saveError && (
            <span
              style={{
                color: '#b91c1c',
                fontSize: 12,
              }}
            >
              {saveError}
            </span>
          )}


          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              setTestOpen(
                (value) =>
                  !value
              )
            }
          >
            <MessageSquare size={15} />
            Test chat
          </button>


          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              setJsonOpen(true)
            }
          >
            <FileJson size={15} />
            JSON preview
          </button>


          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              setFlow(
                setFlowStatus(
                  flow,
                  flow.status === 'active'
                    ? 'draft'
                    : 'active'
                )
              )
            }
          >
            <Check size={15} />

            {flow.status === 'active'
              ? 'Deactivate'
              : 'Activate'}
          </button>


          <button
            type="button"
            className="primary-button"
            onClick={() =>
              onSave(flow)
            }
            disabled={saving}
          >

            {saving ? (

              <Loader2
                size={15}
                className="spin"
              />

            ) : (

              <Save size={15} />

            )}


            {saving
              ? 'Saving...'
              : 'Save'}

          </button>

        </div>

      </div>


      <div className="builder-body">

        <div className="palette">

          <h3>
            Add a step
          </h3>


          {nodeTypeList
            .filter(
              (type) =>
                type !== 'start'
            )
            .map(
              (type) => (

                <button
                  key={type}
                  type="button"
                  className={`palette-item ${draggingType === type
                      ? 'dragging'
                      : ''
                    }`}

                  draggable

                  onClick={() =>
                    addNode(type)
                  }

                  onDragStart={(
                    event
                  ) =>
                    handleDragStart(
                      event,
                      type
                    )
                  }

                  onDragEnd={
                    handleDragEnd
                  }
                >

                  <span
                    className={`eyebrow ${nodeToneClasses[type]
                      }`}
                  >
                    {nodeIcons[type]}
                  </span>


                  <div>

                    <strong>
                      {
                        NODE_META[
                          type
                        ].label
                      }
                    </strong>


                    <small
                      style={{
                        display:
                          'block',

                        color:
                          '#94a3b8',

                        marginTop:
                          2,
                      }}
                    >
                      {
                        NODE_META[
                          type
                        ].description
                      }
                    </small>

                  </div>

                </button>

              )
            )}


          <div
            style={{
              marginTop: 16,
              padding: '12px 14px',
              borderRadius: 10,
              background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)',
              border: '1px dashed #cbd5e1',
              color: '#64748b',
              fontSize: 11,
              lineHeight: 1.6,
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 18, marginBottom: 4 }}>⬆</div>
            Click a step to add it,
            or drag it onto the canvas.
          </div>

        </div>


        <div
          style={{
            flex: 1,
            minWidth: 0,
            minHeight: 0,
            position: 'relative',
          }}

          onDragOver={
            handleCanvasDragOver
          }

          onDrop={
            handleCanvasDrop
          }
        >

          <FlowCanvas
            flow={flow}
            onChange={setFlow}
            onSelect={setSelected}
          />

        </div>


        {selectedNode && (

          <NodeConfigPanel
            node={selectedNode}
            availableNodes={flow.nodes}
            flowId={flow.flow_id}
            onChange={updateNode}
            onClose={() =>
              setSelected(null)
            }
          />

        )}


        {testOpen &&
          !selectedNode && (

            <TestChatPanel
              flow={flow}
              onClose={() =>
                setTestOpen(false)
              }
            />

          )}

      </div>


      {jsonOpen && (

        <div className="json-modal">

          <div className="json-card">

            <div className="panel-header">

              <h2>
                Flow JSON
              </h2>


              <button
                type="button"
                className="icon-button"
                onClick={() =>
                  setJsonOpen(false)
                }
                aria-label="Close JSON"
              >
                <X size={17} />
              </button>

            </div>


            <pre>
              {flowToJson(flow)}
            </pre>

          </div>

        </div>

      )}

    </div>
  )
}


// ============================================================
// PLACEHOLDER
// ============================================================

function Placeholder({
  title,
  description,
  icon: Icon,
}: {
  title: string
  description: string
  icon: any
}) {

  return (
    <div className="content">

      <div className="page-title">

        <div>

          <h1>
            {title}
          </h1>


          <p>
            {description}
          </p>

        </div>

      </div>


      <div
        className="panel"
        style={{
          minHeight: 360,
          display: 'grid',
          placeItems: 'center',
          textAlign: 'center',
        }}
      >

        <div>

          <div
            className="flow-icon"
            style={{
              margin:
                '0 auto 15px',
            }}
          >
            <Icon size={20} />
          </div>


          <h2
            style={{
              margin: 0,
              fontSize: 16,
            }}
          >
            Nothing here yet
          </h2>


          <p
            style={{
              color:
                '#64748b',

              maxWidth:
                360,

              lineHeight:
                1.5,
            }}
          >
            {title} data isn’t available yet —
            this section is waiting on a backend endpoint.
          </p>

        </div>

      </div>

    </div>
  )
}


// ============================================================
// CONVERSATIONS
// ============================================================

function Conversations() {

  return (
    <div className="content">

      <div className="page-title">

        <div>

          <h1>
            Conversations
          </h1>


          <p>
            Review and respond to customer conversations.
          </p>

        </div>

      </div>


      <div
        className="panel"
        style={{
          minHeight: 420,
          display: 'grid',
          placeItems: 'center',
          textAlign: 'center',
        }}
      >

        <div>

          <div
            className="flow-icon"
            style={{
              margin:
                '0 auto 15px',
            }}
          >
            <MessageSquare size={20} />
          </div>


          <h2
            style={{
              margin: 0,
              fontSize: 16,
            }}
          >
            No conversations available
          </h2>


          <p
            style={{
              color:
                '#64748b',

              maxWidth:
                360,

              lineHeight:
                1.5,
            }}
          >
            This page is wired up and ready to call
            GET /conversations once that endpoint exists
            on the backend.
          </p>

        </div>

      </div>

    </div>
  )
}


// ============================================================
// MAIN PAGE
// ============================================================

export default function Page() {

  // ==========================================================
  // NAVIGATION
  // ==========================================================

  const [current, setCurrent] =
    useState<string>(
      'Dashboard'
    )

  const [mobileOpen, setMobileOpen] =
    useState(false)


  // ==========================================================
  // FLOWS
  // ==========================================================

  const [flows, setFlows] =
    useState<Flow[]>([])

  const [flowsLoading, setFlowsLoading] =
    useState(true)

  const [flowsError, setFlowsError] =
    useState<string | null>(null)


  // ==========================================================
  // EDITING FLOW
  // ==========================================================

  const [editingFlow, setEditingFlow] =
    useState<Flow | null>(null)

  const [flowLoading, setFlowLoading] =
    useState(false)

  const [flowLoadError, setFlowLoadError] =
    useState<string | null>(null)


  // ==========================================================
  // SAVE STATE
  // ==========================================================

  const [saving, setSaving] =
    useState(false)

  const [saveError, setSaveError] =
    useState<string | null>(null)


  // ==========================================================
  // LOAD FLOWS
  // ==========================================================

  const loadFlows = async () => {

    setFlowsLoading(true)

    setFlowsError(null)


    try {

      const data =
        await flowApi.list()


      setFlows(
        Array.isArray(data)
          ? data
          : []
      )

    } catch (error) {

      console.error(
        'Failed to load flows:',
        error
      )


      setFlowsError(
        'Unable to load flows. Make sure the backend is running.'
      )

    } finally {

      setFlowsLoading(false)

    }
  }


  // ==========================================================
  // INITIAL LOAD
  // ==========================================================

  useEffect(
    () => {

      loadFlows()

    },
    []
  )


  // ==========================================================
  // NAVIGATION
  // ==========================================================

  const navigate = (
    view: string
  ) => {

    setCurrent(view)

    setMobileOpen(false)

    setEditingFlow(null)

    setFlowLoading(false)

    setFlowLoadError(null)

    setSaveError(null)

  }


  // ==========================================================
  // OPEN FLOW
  // ==========================================================

  const openFlow = async (
    flow: Flow
  ) => {

    setCurrent('Flows')

    setFlowLoading(true)

    setFlowLoadError(null)

    setSaveError(null)


    try {

      const full =
        await flowApi.get(
          flow.flow_id
        )


      if (full) {

        setEditingFlow(
          full
        )

      } else {

        setEditingFlow(
          flow
        )

      }

    } catch (error) {

      console.error(
        'Failed to load flow:',
        error
      )


      setFlowLoadError(
        'Unable to load this flow from the backend.'
      )


      setEditingFlow(
        flow
      )

    } finally {

      setFlowLoading(false)

    }
  }


  // ==========================================================
  // CREATE FLOW
  // ==========================================================

  const createFlow = () => {

    const fresh =
      emptyFlow()


    const startNode =
      createNode(
        'start',
        0
      )


    const newFlow: Flow = {

      ...fresh,

      name:
        'Untitled flow',

      nodes: [
        startNode,
      ],

    }


    setCurrent('Flows')

    setFlowLoadError(null)

    setSaveError(null)

    setEditingFlow(
      newFlow
    )
  }


  // ==========================================================
  // SAVE FLOW
  // ==========================================================

  const saveFlow = async (
    flow: Flow
  ) => {

    if (!flow) {
      return
    }


    setSaving(true)

    setSaveError(null)


    try {

      console.log(
        'Saving flow:',
        flow
      )


      const saved =
        await flowApi.save(
          flow
        )


      console.log(
        'Flow saved:',
        saved
      )


      setEditingFlow(
        saved
      )


      setFlows(
        (items) => {

          const exists =
            items.some(
              (item) =>
                item.flow_id ===
                saved.flow_id
            )


          if (exists) {

            return items.map(
              (item) =>
                item.flow_id ===
                  saved.flow_id
                  ? saved
                  : item
            )

          }


          return [
            saved,
            ...items,
          ]
        }
      )

    } catch (error) {

      console.error(
        'Failed to save flow:',
        error
      )


      setSaveError(
        'Unable to save. Make sure the backend is running.'
      )

    } finally {

      setSaving(false)

    }
  }


  // ==========================================================
  // RENAME FLOW
  // ==========================================================

  const renameFlow = async (
    flow: Flow,
    newName: string
  ) => {

    try {

      const renamed =
        await flowApi.rename(
          flow.flow_id,
          newName
        )


      const updatedName =
        renamed.name ||
        newName


      // Update flow list
      setFlows(
        (items) =>
          items.map(
            (item) =>
              item.flow_id ===
                flow.flow_id
                ? {
                  ...item,
                  ...renamed,
                  name:
                    updatedName,
                }
                : item
          )
      )


      // Update currently opened flow
      if (
        editingFlow?.flow_id ===
        flow.flow_id
      ) {

        setEditingFlow(
          {
            ...editingFlow,
            ...renamed,
            name:
              updatedName,
          }
        )

      }

    } catch (error) {

      console.error(
        'Failed to rename flow:',
        error
      )

      throw error

    }
  }


  // ==========================================================
  // DELETE FLOW
  // ==========================================================

  const deleteFlow = async (
    flow: Flow
  ) => {

    try {

      await flowApi.delete(
        flow.flow_id
      )


      // Remove from flow list
      setFlows(
        (items) =>
          items.filter(
            (item) =>
              item.flow_id !==
              flow.flow_id
          )
      )


      // If deleted flow was open,
      // return to flows page.
      if (
        editingFlow?.flow_id ===
        flow.flow_id
      ) {

        setEditingFlow(null)

        setCurrent('Flows')

        setFlowLoading(false)

        setFlowLoadError(null)

        setSaveError(null)

      }

    } catch (error) {

      console.error(
        'Failed to delete flow:',
        error
      )

      throw error

    }
  }


  // ==========================================================
  // CONTENT
  // ==========================================================

  let content:
    React.ReactNode


  // ==========================================================
  // BUILDER
  // ==========================================================

  if (editingFlow) {

    if (flowLoading) {

      content = (

        <div className="content">

          <div
            className="panel"
            style={{
              padding: 60,
              textAlign:
                'center',
            }}
          >

            <Loader2
              size={18}
              className="spin"
            />


            <div
              style={{
                marginTop: 10,
              }}
            >
              Loading flow...
            </div>

          </div>

        </div>

      )

    } else {

      content = (

        <Builder

          flow={
            editingFlow
          }

          setFlow={
            setEditingFlow
          }

          onBack={() => {

            setEditingFlow(
              null
            )

            setFlowLoading(
              false
            )

            setFlowLoadError(
              null
            )

            setSaveError(
              null
            )

            setCurrent(
              'Flows'
            )

          }}

          onSave={
            saveFlow
          }

          saving={
            saving
          }

          saveError={
            saveError ??
            flowLoadError
          }

        />

      )
    }


    // ==========================================================
    // DASHBOARD
    // ==========================================================

  } else if (
    current ===
    'Dashboard'
  ) {

    content = (

      <Dashboard

        flows={
          flows
        }

        flowsLoading={
          flowsLoading
        }

        flowsError={
          flowsError
        }

        onNavigate={
          navigate
        }

        onCreateFlow={
          createFlow
        }

      />

    )


    // ==========================================================
    // FLOWS
    // ==========================================================

  } else if (
    current ===
    'Flows'
  ) {

    content = (

      <Flows

        flows={
          flows
        }

        loading={
          flowsLoading
        }

        error={
          flowsError
        }

        onOpen={
          openFlow
        }

        onCreate={
          createFlow
        }

        onRetry={
          loadFlows
        }

        onRename={
          renameFlow
        }

        onDelete={
          deleteFlow
        }

      />

    )


    // ==========================================================
    // CONVERSATIONS
    // ==========================================================

  } else if (
    current ===
    'Conversations'
  ) {

    content = (
      <Conversations />
    )


    // ==========================================================
    // CUSTOMERS
    // ==========================================================

  } else if (
    current ===
    'Customers'
  ) {

    content = (

      <Placeholder

        title="Customers"

        description={
          'A single view of everyone who has chatted with your assistant.'
        }

        icon={
          Users
        }

      />

    )


    // ==========================================================
    // AUTOMATIONS
    // ==========================================================

  } else if (
    current ===
    'Automations'
  ) {

    content = (

      <Placeholder

        title="Automations"

        description={
          'Trigger actions when conversations match your rules.'
        }

        icon={
          Zap
        }

      />

    )


    // ==========================================================
    // APPOINTMENTS
    // ==========================================================

  } else if (
    current ===
    'Appointments'
  ) {

    content = (

      <Placeholder

        title="Appointments"

        description={
          'Keep track of demos and meetings booked through your flows.'
        }

        icon={
          CalendarDays
        }

      />

    )


    // ==========================================================
    // SETTINGS
    // ==========================================================

  } else {

    content = (

      <Placeholder

        title="Settings"

        description={
          'Manage your workspace, channels, and assistant preferences.'
        }

        icon={
          Settings
        }

      />

    )
  }


  // ==========================================================
  // PAGE
  // ==========================================================

  return (

    <div className="app-shell">

      <Sidebar

        current={
          current
        }

        setCurrent={
          navigate
        }

      />


      <main className="main-area">

        <Topbar

          current={
            editingFlow
              ? 'Edit Flow'
              : current
          }

          onMenu={() =>
            setMobileOpen(
              (value) =>
                !value
            )
          }

        />


        {content}

      </main>


      {mobileOpen && (

        <div className="mobile-menu">

          <Sidebar

            current={
              current
            }

            setCurrent={
              navigate
            }

          />

        </div>

      )}

    </div>
  )
}

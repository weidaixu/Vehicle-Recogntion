import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError, api } from './api'

const { agentResponse } = vi.hoisted(() => ({ agentResponse: {
  session_id: 'session-test', answer: '已完成车型研究。',
  classification: { label: '0000', name: '江铃_凯运', confidence: .93, rejected: false, top_k: [{ label: '0000', name: '江铃_凯运', confidence: .93 }] },
  design_language: { summary: '低重心', proportions: '紧凑', lighting_signature: '横向', surface_language: '收紧', aerodynamics: '未知', brand_cues: '未知', limitations: '仅图像观察', trace_id: 't1' },
  views: [], board_url: null,
  trace: [{ tool: 'classify_car', status: 'success', arguments: { image_ref: 'img-1.jpg' }, result: { label: '0000' }, duration_ms: 12, call_id: 'c1' }],
} }))

vi.mock('./components/DepthBackground', () => ({ default: () => <div aria-hidden="true" /> }))
vi.mock('./api', async () => {
  const actual = await vi.importActual<typeof import('./api')>('./api')
  return {
    ...actual,
    api: {
      status: vi.fn().mockResolvedValue({ model_ready: true, class_count: 51, macro_f1: .84, deepseek_configured: true, webgl_assets_ready: true }),
      agentUpload: vi.fn().mockResolvedValue(agentResponse),
      agentMessage: vi.fn().mockResolvedValue({ ...agentResponse, answer: '已沿用同一会话继续检索。', trace: [{ ...agentResponse.trace[0], tool: 'search_archive_history' }] }),
      archives: vi.fn().mockResolvedValue({ items: [{ archive_id: 'a1', title: '车展观察', class_id: '0000', created_at: '2026-09-10T00:00:00Z' }] }),
    },
  }
})

describe('DriveScope agent workspace', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => cleanup())

  it('submits an uploaded image with a natural-language task and renders the real trace', async () => {
    render(<App />)
    const input = screen.getByLabelText('上传车辆照片')
    const file = new File(['image'], 'car.jpg', { type: 'image/jpeg' })
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.change(screen.getByLabelText('给智能体的任务'), { target: { value: '识别并建立视觉档案' } })
    fireEvent.click(screen.getByRole('button', { name: '执行任务' }))

    await waitFor(() => expect(screen.getByText('已完成车型研究。')).toBeTruthy())
    expect(screen.getByText('classify_car')).toBeTruthy()
    expect(screen.getByText(/image_ref/)).toBeTruthy()
  })

  it('continues the same session from the chat composer and loads archive history', async () => {
    render(<App />)
    fireEvent.change(screen.getByLabelText('给智能体的任务'), { target: { value: '检索我之前保存的档案' } })
    fireEvent.click(screen.getByRole('button', { name: '发送追问' }))
    await waitFor(() => expect(screen.getByText('已沿用同一会话继续检索。')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: '查看历史档案' }))
    await waitFor(() => expect(screen.getByText('车展观察')).toBeTruthy())
  })

  it('opens the homepage directly without a startup screen', () => {
    render(<App />)
    expect(screen.getByRole('img', { name: 'DriveScope visual background' })).toHaveAttribute('src', '/assets/showroom-original.jpg')
    expect(screen.getByRole('img', { name: 'DriveScope visual background' })).toHaveAttribute('data-rotation', 'left-90')
    expect(document.querySelector('.agent-workspace')).toHaveAttribute('data-layout', 'dialogue-with-tools')
    expect(screen.queryByRole('button', { name: 'Start DriveScope' })).toBeNull()
    expect(document.querySelector('.app')).not.toHaveClass('homepage-hidden')
  })

  it('shows a clear drag-over state for the vehicle image entry', () => {
    render(<App />)
    const dropzone = document.querySelector('.dropzone') as HTMLElement
    fireEvent.dragOver(dropzone)
    expect(dropzone).toHaveClass('is-dragging')
    fireEvent.dragLeave(dropzone)
    expect(dropzone).not.toHaveClass('is-dragging')
  })

  it('marks an agent request failure as a readable alert', async () => {
    vi.mocked(api.agentMessage).mockRejectedValueOnce(new ApiError('DeepSeek API Key 无效或无权限，请重新配置', 502))
    render(<App />)
    fireEvent.change(screen.getByLabelText('给智能体的任务'), { target: { value: '识别这辆车' } })
    fireEvent.click(screen.getByRole('button', { name: '发送追问' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveClass('agent-error')
    expect(alert).toHaveTextContent('DeepSeek API Key 无效或无权限，请重新配置')
  })

  it('uses the visual research dashboard structure from the approved reference', () => {
    render(<App />)

    expect(document.querySelector('.brand-manifesto')).toHaveTextContent('CAPTURE · UNDERSTAND · ARCHIVE')
    expect(document.querySelector('.proof-rail')).toBeTruthy()
    expect(document.querySelector('.agent-workspace')).toHaveAttribute('data-layout', 'dialogue-with-tools')
    expect(document.querySelectorAll('.insight-card')).toHaveLength(4)
  })
})

import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import CharacterCreationModal from '../components/CharacterCreationModal'

// ── Mock api client ────────────────────────────────────────────────────────
vi.mock('../api/client', () => ({
  api: {
    post: vi.fn(),
  },
}))

import { api } from '../api/client'
const mockApiPost = vi.mocked(api.post)

// ── Helpers ────────────────────────────────────────────────────────────────
const defaultProps = {
  isOpen:     true,
  onClose:    vi.fn(),
  campaignId: 'test-campaign-id',
  onCreate:   vi.fn(),
}

function renderModal(props = {}) {
  return render(<CharacterCreationModal {...defaultProps} {...props} />)
}

// ── Tests ──────────────────────────────────────────────────────────────────
describe('CharacterCreationModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders mode selector on open', () => {
    renderModal()
    expect(screen.getByText('Criar Manualmente')).toBeInTheDocument()
    expect(screen.getByText('Gerar com IA')).toBeInTheDocument()
  })

  it('navigates to manual wizard when Criar Manualmente is clicked', async () => {
    renderModal()
    await userEvent.click(screen.getByText('Criar Manualmente'))
    expect(screen.getByText('Character Name')).toBeInTheDocument()
    // Step indicator should be visible
    expect(screen.getByText('Identity')).toBeInTheDocument()
  })

  it('shows AI description form when Gerar com IA is clicked', async () => {
    renderModal()
    await userEvent.click(screen.getByText('Gerar com IA'))
    expect(screen.getByPlaceholderText(/elfo renegado/i)).toBeInTheDocument()
    expect(screen.getByText('Gerar Personagem')).toBeInTheDocument()
  })

  it('shows validation error when AI form is submitted empty', async () => {
    renderModal()
    await userEvent.click(screen.getByText('Gerar com IA'))
    await userEvent.click(screen.getByText('Gerar Personagem'))
    expect(screen.getByText('Descreva como deve ser o personagem.')).toBeInTheDocument()
  })

  it('calls API and pre-fills form on AI generation success', async () => {
    mockApiPost.mockResolvedValueOnce({
      name:             'Zara',
      race:             'Elf',
      character_class:  'Wizard',
      alignment:        'Lawful Good',
      background:       'Scholar',
      appearance:       'Tall and slender with silver hair',
      backstory:        'Exiled from the elven court',
      pixel_art_prompt: 'An elven wizard...',
    })

    renderModal()
    await userEvent.click(screen.getByText('Gerar com IA'))

    const textarea = screen.getByPlaceholderText(/elfo renegado/i)
    await userEvent.type(textarea, 'An elven wizard exiled from her court')
    await userEvent.click(screen.getByText('Gerar Personagem'))

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        '/campaigns/test-campaign-id/generate-character-8bit',
        { description: 'An elven wizard exiled from her court' },
      )
    })

    // After AI generation, should switch to manual wizard with pre-filled name
    await waitFor(() => {
      expect(screen.getByDisplayValue('Zara')).toBeInTheDocument()
    })
  })

  it('shows error on AI generation failure', async () => {
    mockApiPost.mockRejectedValueOnce(new Error('Network error'))

    renderModal()
    await userEvent.click(screen.getByText('Gerar com IA'))

    const textarea = screen.getByPlaceholderText(/elfo renegado/i)
    await userEvent.type(textarea, 'A warrior')
    await userEvent.click(screen.getByText('Gerar Personagem'))

    await waitFor(() => {
      expect(screen.getByText('Falha ao gerar personagem. Tente novamente.')).toBeInTheDocument()
    })
  })

  // Helper: find a button by partial text, tolerating mixed SVG children.
  // Walks all buttons and checks if any child text node contains the string.
  function findBtnWithText(text: string): HTMLElement | undefined {
    return screen.queryAllByRole('button').find((btn: HTMLElement) => {
      const t = (btn.textContent ?? '').replace(/\s+/g, ' ').trim()
      return t.toLowerCase().includes(text.toLowerCase())
    })
  }

  async function waitForBtnWithText(text: string): Promise<HTMLElement> {
    let btn: HTMLElement | undefined
    await waitFor(() => {
      btn = findBtnWithText(text)
      if (!btn) throw new Error(`Button with text "${text}" not found`)
    })
    return btn!
  }

  it('advances through manual wizard steps', async () => {
    renderModal()
    fireEvent.click(screen.getByText('Criar Manualmente'))

    // Step 1: fill name via fireEvent (synchronous, bypasses userEvent async issues)
    const nameInput = await screen.findByPlaceholderText('Aragorn Elessar')
    fireEvent.change(nameInput, { target: { value: 'Thorin' } })

    const nextBtn = await waitForBtnWithText('Next: Attributes')
    fireEvent.click(nextBtn)

    // Step 2 should render the apply button
    expect(await waitForBtnWithText('Apply Standard Array')).toBeTruthy()
  })

  it('validates name on step 1', async () => {
    renderModal()
    fireEvent.click(screen.getByText('Criar Manualmente'))

    await screen.findByPlaceholderText('Aragorn Elessar')
    const nextBtn = await waitForBtnWithText('Next: Attributes')
    fireEvent.click(nextBtn)

    expect(await screen.findByText('Character name is required.')).toBeInTheDocument()
  })

  it('submits character creation from step 3', async () => {
    const mockCharacter = { id: 'char-1', name: 'Thorin' }
    mockApiPost.mockResolvedValueOnce(mockCharacter)

    renderModal()
    fireEvent.click(screen.getByText('Criar Manualmente'))

    // Step 1 → 2
    const nameInput = await screen.findByPlaceholderText('Aragorn Elessar')
    fireEvent.change(nameInput, { target: { value: 'Thorin' } })
    fireEvent.click(await waitForBtnWithText('Next: Attributes'))

    // Step 2 → 3
    fireEvent.click(await waitForBtnWithText('Next: Personality'))

    // Step 3 → submit
    fireEvent.click(await waitForBtnWithText('Create Character'))

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        '/characters',
        expect.objectContaining({ name: 'Thorin', class: 'Guerreiro' }),
      )
      expect(defaultProps.onCreate).toHaveBeenCalledWith(mockCharacter)
    })
  })

  it('resets to mode select when modal is reopened', async () => {
    const { rerender } = renderModal()
    await userEvent.click(screen.getByText('Criar Manualmente'))
    // Should be in wizard mode
    expect(await screen.findByPlaceholderText('Aragorn Elessar')).toBeInTheDocument()

    // Close and reopen — useEffect resets state
    rerender(<CharacterCreationModal {...defaultProps} isOpen={false} />)
    rerender(<CharacterCreationModal {...defaultProps} isOpen={true} />)

    // Back to mode select
    expect(await screen.findByText('Criar Manualmente')).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Aragorn Elessar')).not.toBeInTheDocument()
  })
})

import type { Character } from "../api";
import { useLocale } from "../i18n";
import {
  buildPlotCharacterList,
  listAvatarSlotInstances,
  upsertPlotBinding,
  type PlotCastBinding,
  type SceneGraph,
} from "../sceneGraph";

type Props = {
  graph: SceneGraph;
  characters: Character[];
  playerCharacter?: Record<string, unknown> | null;
  bindings: PlotCastBinding[];
  onChange: (bindings: PlotCastBinding[]) => void;
};

export default function PlotCastBindingPanel({
  graph,
  characters,
  playerCharacter,
  bindings,
  onChange,
}: Props) {
  const { t } = useLocale();
  const plotChars = buildPlotCharacterList(characters, playerCharacter);
  const slots = listAvatarSlotInstances(graph);

  const bindingMap = new Map(bindings.map((b) => [b.character_id, b.instance_id]));

  return (
    <section className="plot-cast-binding">
      <h2>{t.sceneVisual.plotBindingSection}</h2>
      <p className="muted">{t.sceneVisual.plotBindingHint}</p>

      {slots.length === 0 && <p className="muted">{t.sceneVisual.plotBindingNoSlots}</p>}

      <table className="data-table">
        <thead>
          <tr>
            <th>{t.sceneVisual.plotCharacter}</th>
            <th>{t.sceneVisual.avatarSlot}</th>
          </tr>
        </thead>
        <tbody>
          {plotChars.map((pc) => (
            <tr key={pc.character_id}>
              <td>
                <strong>{pc.label}</strong>
                <code>{pc.character_id}</code>
              </td>
              <td>
                <select
                  value={bindingMap.get(pc.character_id) ?? ""}
                  onChange={(e) =>
                    onChange(upsertPlotBinding(bindings, pc.character_id, e.target.value))
                  }
                >
                  <option value="">{t.sceneVisual.unbound}</option>
                  {slots.map((slot) => (
                    <option key={slot.id} value={slot.id}>
                      {slot.editor_label} ({slot.id})
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

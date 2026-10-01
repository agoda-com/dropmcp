import { useCallback, useEffect, useRef } from 'react';
import type { CatalogItem } from '../../api/catalog';
import { subscribeGroup, unsubscribeGroup } from '../../api/subscriptions';
import { useCatalog } from '../../context/CatalogContext';
import { formatName } from '../../utils/format';
import styles from './SearchToolbar.module.css';

type CheckboxState = 'checked' | 'unchecked' | 'indeterminate';

interface Props {
  groups: string[];
  allItems: CatalogItem[];
}

export default function GroupSubscriptionFilter({ groups, allItems }: Props) {
  const {
    subscriptionControlsEnabled,
    subscribedGroups,
    updateGroupSubscriptions,
  } = useCatalog();

  const groupMembers = useCallback(
    (group: string) => allItems.filter((item) => item.group === group),
    [allItems],
  );

  const groupState = useCallback(
    (group: string): CheckboxState => {
      if (!subscribedGroups.includes(group)) return 'unchecked';
      const members = groupMembers(group);
      if (members.length === 0) return 'checked';
      const subscribedCount = members.filter((m) => m.subscribed).length;
      if (subscribedCount === members.length) return 'checked';
      return 'indeterminate';
    },
    [groupMembers, subscribedGroups],
  );

  const handleGroupCheckbox = async (
    group: string,
    nextChecked: boolean,
  ) => {
    if (!subscriptionControlsEnabled) return;

    const members = groupMembers(group);
    updateGroupSubscriptions(group, members, nextChecked);
    try {
      if (nextChecked) {
        await subscribeGroup(group);
      } else {
        await unsubscribeGroup(group);
      }
    } catch {
      updateGroupSubscriptions(group, members, !nextChecked);
    }
  };

  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>Skill groups</span>
      <div className={styles.categories}>
        {groups.map((group) => (
          <GroupSubscriptionPill
            key={group}
            group={group}
            checkboxState={groupState(group)}
            disabled={!subscriptionControlsEnabled}
            onCheckboxToggle={(checked) => handleGroupCheckbox(group, checked)}
          />
        ))}
      </div>
    </div>
  );
}

function GroupSubscriptionPill({
  group,
  checkboxState,
  disabled = false,
  onCheckboxToggle,
}: {
  group: string;
  checkboxState: CheckboxState;
  disabled?: boolean;
  onCheckboxToggle: (checked: boolean) => void;
}) {
  const checkboxRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (checkboxRef.current) {
      checkboxRef.current.indeterminate = checkboxState === 'indeterminate';
    }
  }, [checkboxState]);

  return (
    <label
      className={`${styles.pill} ${styles.groupPill} ${
        checkboxState !== 'unchecked' ? styles.active : ''
      } ${disabled ? styles.disabledPill : ''}`}
      title={disabled ? 'User identity required to change group subscriptions' : undefined}
    >
      <input
        ref={checkboxRef}
        type="checkbox"
        className={styles.groupCheckbox}
        checked={checkboxState === 'checked'}
        disabled={disabled}
        aria-label={`Subscribe to all in ${group}`}
        onChange={() => {
          if (!disabled) onCheckboxToggle(checkboxState !== 'checked');
        }}
      />
      <span>{formatName(group)}</span>
    </label>
  );
}

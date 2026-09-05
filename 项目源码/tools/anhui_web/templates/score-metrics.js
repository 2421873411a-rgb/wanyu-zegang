(() => {
  /* The build pipeline is authoritative for score semantics; the browser only
     accepts an explicitly annotated, same-scale observation. */
  const fromRecord = (record) => {
    const observation = record?.score_observation;
    return observation && typeof observation === 'object' ? observation : null;
  };
  const isComparable = (observation, expectedScale) => Boolean(
    observation
    && observation.status === 'comparable'
    && observation.scale_id === expectedScale
    && Number.isFinite(Number(observation.value))
    && Number(observation.value) > 0
  );
  window.wanyuScoreMetrics = Object.freeze({ fromRecord, isComparable });
})();

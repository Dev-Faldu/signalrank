/* SignalRank in-browser scorer: the exact Spark GBT champion, exported to JSON.
   P(matters) = sigmoid(2 * sum_i w_i * tree_i(x))  (Spark GBT, log-loss). */
(function (root) {
  function walk(n, x) {
    while (n.p === undefined) {
      const v = x[n.f];
      const left = n.op === "le" ? v <= n.v : n.v.indexOf(v) !== -1;
      n = left ? n.l : n.r;
    }
    return n.p;
  }
  function catIndex(model, col, value) {
    const vocab = model.vocab[col] || [];
    const capped = vocab.indexOf(value) !== -1 ? value : "OTHER";
    const i = model.categories[col].indexOf(capped);
    return i === -1 ? model.categories[col].length : i; // unseen -> len(labels), as StringIndexer(handleInvalid=keep)
  }
  function vector(model, row) {
    return model.features.map(function (f) {
      if (f.slice(-3) === "_ix") return catIndex(model, f.slice(0, -3), String(row[f.slice(0, -3)]));
      const v = Number(row[f]);
      return isFinite(v) ? v : 0;
    });
  }
  function score(model, row) {
    const x = vector(model, row);
    let s = 0;
    for (let i = 0; i < model.trees.length; i++) s += model.weights[i] * walk(model.trees[i], x);
    return 1 / (1 + Math.exp(-2 * s));
  }
  const api = { score: score, vector: vector };
  if (typeof module !== "undefined") module.exports = api; else root.GBT = api;
})(typeof self !== "undefined" ? self : this);

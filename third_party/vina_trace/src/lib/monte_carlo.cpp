/*

   Copyright (c) 2006-2010, The Scripps Research Institute

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

   Author: Dr. Oleg Trott <ot14@columbia.edu>, 
           The Olson Lab, 
           The Scripps Research Institute

*/

#include "monte_carlo.h"
#include "coords.h"
#include "mutate.h"
#include "quasi_newton.h"
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>

output_type monte_carlo::operator()(model& m, const precalculate_byatom& p, const igrid& ig, const vec& corner1, const vec& corner2, incrementable* increment_me, rng& generator, int trace_task) const {
	output_container tmp;
	this->operator()(m, tmp, p, ig, corner1, corner2, increment_me, generator, trace_task); // call the version that produces the whole container
	VINA_CHECK(!tmp.empty());
	return tmp.front();
}

bool metropolis_accept(fl old_f, fl new_f, fl temperature, rng& generator) {
	if(new_f < old_f) return true;
	const fl acceptance_probability = std::exp((old_f - new_f) / temperature);
	return random_fl(0, 1, generator) < acceptance_probability;
}

// out is sorted
void monte_carlo::operator()(model& m, output_container& out, const precalculate_byatom& p, const igrid& ig, const vec& corner1, const vec& corner2, incrementable* increment_me, rng& generator, int trace_task) const {
    int evalcount = 0;
	vec authentic_v(1000, 1000, 1000); // FIXME? this is here to avoid max_fl/max_fl
	conf_size s = m.get_size();
	change g(s);
	output_type tmp(s, 0);
	tmp.c.randomize(corner1, corner2, generator);
	fl best_e = max_fl;
	quasi_newton quasi_newton_par;
    quasi_newton_par.max_steps = local_steps;
	const char* trace_prefix = std::getenv("VINA_TRACE_PREFIX");
	const bool tracing = trace_prefix && *trace_prefix && trace_task >= 0;
	std::ofstream csv;
	std::ofstream snapshots;
	if(tracing && trace_task == 0) {
		csv.open(std::string(trace_prefix) + "_task_0.csv");
		csv << "task,step,accepted,candidate_energy,retained_energy,best_energy\n";
		snapshots.open(std::string(trace_prefix) + "_task_0.pdbqt");
	}
	unsigned steps_done = 0;
	unsigned accepted_count = 0;
	unsigned snapshot_count = 0;
	const unsigned sample_every = std::max(1u, global_steps / 60u);
	VINA_U_FOR(step, global_steps) {
		if(increment_me)
			++(*increment_me);
		if((max_evals > 0) & (evalcount > max_evals))
			break;
		output_type candidate = tmp;
		mutate_conf(candidate.c, m, mutation_amplitude, generator);
		quasi_newton_par(m, p, ig, candidate, g, hunt_cap, evalcount);
		const fl candidate_energy = candidate.e;
		const bool accepted = step == 0 || metropolis_accept(tmp.e, candidate.e, temperature, generator);
		if(accepted) {
			++accepted_count;
			tmp = candidate;

			// FIXME only for very promising ones
			if(tmp.e < best_e || out.size() < num_saved_mins) {
				quasi_newton_par(m, p, ig, tmp, g, authentic_v, evalcount);
				tmp.coords = m.get_heavy_atom_movable_coords();
				add_to_output_container(out, tmp, min_rmsd, num_saved_mins); // 20 - max size
				if(tmp.e < best_e)
					best_e = tmp.e;
			}
		}
		++steps_done;
		if(csv) csv << trace_task << ',' << (step + 1) << ',' << accepted << ','
		             << std::setprecision(17) << candidate_energy << ',' << tmp.e << ',' << best_e << '\n';
		if(snapshots && (step == 0 || (step + 1) % sample_every == 0 || step + 1 == global_steps)) {
			// Capture is observational: never change the live search model.
			model sampled_model = m;
			sampled_model.set(tmp.c);
			std::ostringstream remark;
			remark << "REMARK VINA TRACE TASK " << trace_task << " STEP " << (step + 1)
			       << " ACCEPTED " << accepted << " ENERGY " << std::setprecision(17) << tmp.e << '\n';
			snapshots << sampled_model.write_model(++snapshot_count, remark.str());
		}
	}
	if(tracing) {
		std::ofstream summary(std::string(trace_prefix) + "_task_" + std::to_string(trace_task) + "_summary.txt");
		summary << "task=" << trace_task << "\nsteps=" << steps_done << "\naccepted=" << accepted_count
		        << "\nbest_energy=" << std::setprecision(17) << best_e << "\n";
	}
	VINA_CHECK(!out.empty());
	VINA_CHECK(out.front().e <= out.back().e); // make sure the sorting worked in the correct order
}
